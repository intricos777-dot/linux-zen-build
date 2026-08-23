#!/bin/bash
# BTC Solo Miner - CPU mining to solo.ckpool.org
# Address: 33oBrFCtn7SvqULsERymwtwmM8mXSrgcd9

exec /usr/bin/cpuminer \
  --algo=sha256d \
  --url=stratum+tcp://solo.ckpool.org:3333 \
  --user=33oBrFCtn7SvqULsERymwtwmM8mXSrgcd9 \
  --pass=x \
  --threads=4 \
  --retry-pause=10 \
  --cpu-affinity=0xF