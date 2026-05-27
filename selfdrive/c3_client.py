#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C3 Client — 部署到 C3 设备上
与 C3 Director 服务端通信
支持远程指令执行、tmux 故障诊断、心跳保活

通过 openpilot 的 PythonProcess 自动启动：
  PythonProcess("c3-client", "selfdrive.c3_client", always_run),

零外部依赖（内嵌纯 Python 版 WebSocket 客户端，纯标准库实现）
"""

import asyncio
import base64
import json
import os
import random
import struct
import subprocess
import sys
import traceback
import urllib.parse
from datetime import datetime

# openpilot 基础模块
from openpilot.system.hardware import HARDWARE, PC
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog


# ================= 内嵌 WebSocket 客户端（纯标准库） =================

class _WebSocketError(Exception):
  pass


class _WebSocketClient:
  """异步 WebSocket 客户端（RFC 6455），仅依赖 Python 标准库"""

  def __init__(self, url, ping_interval=20, ping_timeout=15):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("ws",):
      raise ValueError(f"不支持的协议: {parsed.scheme}")
    self.host = parsed.hostname
    self.port = parsed.port or 80
    self.path = parsed.path or "/"
    if parsed.query:
      self.path += "?" + parsed.query

    self.ping_interval = ping_interval
    self.ping_timeout = ping_timeout
    self._reader = None
    self._writer = None
    self._closed = False
    self._recv_queue = asyncio.Queue()
    self._pong_event = asyncio.Event()

  async def connect(self):
    """建立 TCP + WebSocket 握手"""
    try:
      self._reader, self._writer = await asyncio.wait_for(
        asyncio.open_connection(self.host, self.port), timeout=10
      )

      # 生成 Sec-WebSocket-Key
      rand_bytes = bytes(random.randint(0, 255) for _ in range(16))
      ws_key = base64.b64encode(rand_bytes).decode()

      request = (
        f"GET {self.path} HTTP/1.1\r\n"
        f"Host: {self.host}:{self.port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
      )
      self._writer.write(request.encode())
      await self._writer.drain()

      # 读取响应头
      response = b""
      while b"\r\n\r\n" not in response:
        chunk = await asyncio.wait_for(self._reader.read(4096), timeout=10)
        if not chunk:
          raise _WebSocketError("连接关闭")
        response += chunk

      header_text = response.decode("utf-8", errors="replace")
      status_line = header_text.split("\r\n")[0]
      if "101" not in status_line:
        raise _WebSocketError(f"握手失败: {status_line}")

      self._recv_task = asyncio.create_task(self._recv_loop())
      self._ping_task = asyncio.create_task(self._ping_loop())
    except asyncio.TimeoutError:
      raise _WebSocketError("连接或握手超时")

  async def _recv_loop(self):
    """持续读取 WebSocket 帧"""
    try:
      while not self._closed:
        frame = await self._read_frame()
        if frame is None:
          break

        opcode = frame[0] & 0x0F
        payload = frame[1]

        if opcode in (0x0, 0x1):  # 继续帧 / 文本帧
          await self._recv_queue.put(("text", payload.decode("utf-8", errors="replace")))
        elif opcode == 0x8:  # 关闭帧
          await self._send_close()
          self._closed = True
          break
        elif opcode == 0x9:  # Ping → 自动 Pong
          await self._send_frame(0xA, payload)
        elif opcode == 0xA:  # Pong
          self._pong_event.set()
    except (asyncio.CancelledError, ConnectionError):
      pass
    except Exception as e:
      print(f"[C3] WebSocket 接收异常: {e}")
    finally:
      self._closed = True

  async def _read_frame(self):
    """读取一个 WebSocket 帧"""
    header = await self._read_exact(2)
    if not header:
      return None

    first_byte = header[0]
    second_byte = header[1]
    length = second_byte & 0x7F

    if length == 126:
      ext = await self._read_exact(2)
      length = struct.unpack("!H", ext)[0]
    elif length == 127:
      ext = await self._read_exact(8)
      length = struct.unpack("!Q", ext)[0]

    mask_key = await self._read_exact(4) if (second_byte & 0x80) else None
    payload = await self._read_exact(length)

    if mask_key:
      payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    return (first_byte, payload)

  async def _read_exact(self, n):
    """精确读取 n 字节"""
    data = b""
    while len(data) < n:
      chunk = await self._reader.read(n - len(data))
      if not chunk:
        raise _WebSocketError("连接断开")
      data += chunk
    return data

  async def send(self, text):
    """发送文本消息"""
    payload = text.encode("utf-8") if isinstance(text, str) else text
    await self._send_frame(0x1, payload)

  async def _send_frame(self, opcode, payload):
    """发送 WebSocket 帧（客户端必须 mask）"""
    header = bytearray()
    header.append(0x80 | opcode)  # FIN + opcode

    length = len(payload)
    if length < 126:
      header.append(0x80 | length)
    elif length < 65536:
      header.append(0x80 | 126)
      header.extend(struct.pack("!H", length))
    else:
      header.append(0x80 | 127)
      header.extend(struct.pack("!Q", length))

    mask_key = bytes(random.randint(0, 255) for _ in range(4))
    header.extend(mask_key)
    header.extend(bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload)))

    self._writer.write(bytes(header))
    await self._writer.drain()

  async def _send_close(self):
    try:
      self._writer.write(bytes([0x88, 0x00]))
      await self._writer.drain()
    except Exception:
      pass

  async def _ping_loop(self):
    try:
      while not self._closed:
        await asyncio.sleep(self.ping_interval)
        self._pong_event.clear()
        await self._send_frame(0x9, b"")
        try:
          await asyncio.wait_for(self._pong_event.wait(), timeout=self.ping_timeout)
        except asyncio.TimeoutError:
          print("[C3] Ping 超时")
          break
    except asyncio.CancelledError:
      pass
    except Exception as e:
      print(f"[C3] Ping 循环异常: {e}")
    finally:
      self._closed = True

  async def recv(self):
    """接收一条消息"""
    while not self._closed:
      msg_type, text = await self._recv_queue.get()
      if msg_type == "text":
        return text
    raise ConnectionError("连接已关闭")

  def __aiter__(self):
    return self._async_iterator()

  async def _async_iterator(self):
    while not self._closed:
      try:
        yield await self.recv()
      except ConnectionError:
        break

  async def close(self):
    self._closed = True
    if self._writer:
      await self._send_close()
      try:
        self._writer.close()
        await self._writer.wait_closed()
      except Exception:
        pass
    for attr in ("_recv_task", "_ping_task"):
      if hasattr(self, attr):
        getattr(self, attr).cancel()

  async def __aenter__(self):
    await self.connect()
    return self

  async def __aexit__(self, *args):
    await self.close()


# ================= 配置 =================
SERVER_URL = "ws://1.15.136.221:8500"
HEARTBEAT_INTERVAL = 15
RECONNECT_DELAY = 5

# ================= 设备标识 =================
_params = Params()


def get_serial():
  try:
    return HARDWARE.get_serial()
  except Exception:
    return os.uname().nodename


def get_dongle_id():
  try:
    dongle = _params.get("DongleId")
    return dongle if dongle else ""
  except Exception:
    return ""


def get_git_branch():
  try:
    result = subprocess.run(
      ["git", "rev-parse", "--abbrev-ref", "HEAD"],
      capture_output=True, text=True, timeout=5,
      cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return result.stdout.strip() if result.returncode == 0 else ""
  except Exception:
    return ""

def get_car_platform():
  try:
    bundle = _params.get("CarPlatformBundle")
    if bundle:
      if isinstance(bundle, dict):
        return bundle.get("name", "")
      import json
      return json.loads(bundle).get("name", "")
    return ""
  except Exception:
    return ""


# ================= 指令执行 =================
async def execute_cmd(command, timeout=30):
  try:
    result = await asyncio.wait_for(
      asyncio.create_subprocess_shell(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
      ),
      timeout=timeout
    )
    stdout, _ = await result.communicate()
    return {
      "status": "ok",
      "output": stdout.decode(errors="replace"),
      "returncode": result.returncode
    }
  except asyncio.TimeoutError:
    return {"status": "error", "output": "命令执行超时"}
  except Exception as e:
    return {"status": "error", "output": str(e)}


async def execute_tmux():
  tmux_check = await execute_cmd("ps aux | grep tmux | grep -v grep", timeout=3)
  if not tmux_check.get("output", "").strip():
    return {"status": "ok", "output": "⚠️ 设备上未检测到 tmux 进程运行"}

  sessions_result = await execute_cmd("tmux list-sessions 2>&1", timeout=3)
  if "error" in sessions_result.get("output", ""):
    return {"status": "ok", "output": f"⚠️ 无法获取 tmux 会话\n{sessions_result['output']}"}

  result = await execute_cmd(
    "tmux capture-pane -t $(tmux list-sessions -F '#{session_name}' 2>/dev/null | head -1) -p -S -200 2>/dev/null",
    timeout=5
  )
  if result["status"] == "ok" and result.get("output", "").strip():
    session_info = await execute_cmd("tmux list-sessions 2>&1", timeout=3)
    output = f"--- tmux sessions ---\n{session_info.get('output', '')}\n\n--- capture output ---\n{result['output']}"
    return {"status": "ok", "output": output}
  else:
    return {"status": "ok", "output": f"⚠️ 无法捕获 tmux 输出\n{sessions_result.get('output', '')}"}


# ================= 消息处理 =================
async def handle_message(data, ws):
  msg_type = data.get("type")
  msg_id = data.get("id")
  content = data.get("content", "")
  timeout = data.get("timeout", 15)

  if msg_type == "cmd":
    result = await execute_cmd(content, timeout)
  elif msg_type == "tmux":
    result = await execute_tmux()
  elif msg_type == "ping":
    result = {"status": "ok", "output": "pong"}
  else:
    result = {"status": "error", "output": f"未知指令类型: {msg_type}"}

  response = {
    "type": "result",
    "id": msg_id,
    "status": result["status"],
    "output": result.get("output", "")
  }
  try:
    await ws.send(json.dumps(response))
  except Exception as e:
    print(f"[C3] 发送响应失败: {e}")


# ================= 主循环 =================
async def run():
  serial = get_serial()
  dongle_id = get_dongle_id()
  git_branch = get_git_branch()
  car_platform = get_car_platform()

  print(f"[C3 Director Client] 启动 serial={serial} branch={git_branch} platform={car_platform}")

  while True:
    try:
      async with _WebSocketClient(
        SERVER_URL,
        ping_interval=20,
        ping_timeout=15
      ) as ws:
        print(f"[C3] ✅ 已连接服务器")

        register_msg = json.dumps({
          "type": "register",
          "serial": serial,
          "dongle_id": dongle_id,
          "git_branch": git_branch,
          "car_platform": car_platform
        })
        await ws.send(register_msg)
        print(f"[C3] 已注册: {serial} branch={git_branch}")

        async def heartbeat():
          while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
              await ws.send(json.dumps({"type": "heartbeat"}))
            except Exception:
              break

        async def receiver():
          async for message in ws:
            try:
              data = json.loads(message)
              await handle_message(data, ws)
            except json.JSONDecodeError:
              pass
            except Exception as e:
              print(f"[C3] 处理消息出错: {e}")
              traceback.print_exc()

        await asyncio.wait_for(asyncio.gather(heartbeat(), receiver()), timeout=65)

    except (ConnectionError, OSError, _WebSocketError):
      print(f"[C3] 连接断开")
    except ConnectionRefusedError:
      print(f"[C3] 服务器拒绝连接")
    except OSError as e:
      print(f"[C3] 网络错误: {e}")
    except asyncio.TimeoutError:
      print(f"[C3] 连接超时")
    except Exception as e:
      print(f"[C3] 异常: {e}")
      traceback.print_exc()

    print(f"[C3] {RECONNECT_DELAY} 秒后重连...")
    await asyncio.sleep(RECONNECT_DELAY)


# ================= 入口 =================
def main():
  try:
    asyncio.run(run())
  except KeyboardInterrupt:
    print("[C3] 客户端已停止")
  except Exception as e:
    print(f"[C3] 致命错误: {e}")
    traceback.print_exc()


if __name__ == "__main__":
  main()
