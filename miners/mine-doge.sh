#!/bin/bash
# DOGE mining - using a known working pool

exec cpuminer --algo=scrypt \
  -o stratum+tcp://scrypt.mine.zpool.ca:3433 \
  -u Dai6AHB6D4M152PWjnHNFF8v.worker1 \
  -p c=DOGE \
  --threads=6 \
  --retry-pause=10 \
  --cpu-affinity=0xAAA
