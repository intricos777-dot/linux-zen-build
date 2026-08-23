#!/bin/bash
# LTC SOLO mining via Viabtc solo pool (supports wallet as username)

exec cpuminer --algo=scrypt \
  -o stratum+tcp://ltc.viabtc.io:3333 \
  -u solo:MQ3qudKtDzSmwg7tHUV7JZTXizLYBtzffj \
  -p x \
  --threads=6 \
  --retry-pause=10 \
  --cpu-affinity=0x555
