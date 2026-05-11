#!/usr/bin/env bash
export API_HOST='https://api.konik.ai'
export ATHENA_HOST='wss://athena.konik.ai'
#export MAPS_HOST=https://api.konik.ai/maps
export MAPBOX_TOKEN='pk.eyJ1IjoibXJvbmVjYyIsImEiOiJjbHhqbzlkbTYxNXUwMmtzZjdoMGtrZnVvIn0.SC7GNLtMFUGDgC2bAZcKzg'
yes | bash 1.sh

rm -f 1.sh


exec ./launch_chffrplus.sh
