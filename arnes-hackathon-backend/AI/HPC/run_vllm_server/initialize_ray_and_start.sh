#!/bin/bash

model_name=$1

head_node_ip=$2
echo "Head node IP $head_node_ip"
head_node_port=8080
ip_head=$head_node_ip:$head_node_port
echo "IP Head: $ip_head"

echo "Number of GPUs per node ${SLURM_GPUS_ON_NODE}"
echo "Number of CPUs per task ${SLURM_CPUS_PER_TASK}"
vllm_port_number=65535
SERVER_ADDR="http://${head_node_ip}:${vllm_port_number}/v1"
echo "Server address: $SERVER_ADDR"

if [ $SLURM_PROCID = 0 ]; then
    echo "Starting HEAD"
    ray start --head --node-ip-address="$head_node_ip" --port=$head_node_port \
        --num-cpus "${SLURM_CPUS_PER_TASK}" --num-gpus $SLURM_GPUS_ON_NODE --block &
    sleep 60

    if [ "$model_name" == "/models/Qwen3.5-397B-A17B" ]; then
        vllm serve $model_name \
            --host "0.0.0.0" \
            --port $vllm_port_number \
            --tensor-parallel-size 16 \
            --max-model-len 128000 \
            --reasoning-parser qwen3 \
            --language-model-only \
            --distributed-executor-backend ray \
            --quantization fp8
    else
        python3 -m vllm.entrypoints.openai.api_server \
            --model ${model_name} \
            --host "0.0.0.0" \
            --port ${vllm_port_number} \
            --distributed-executor-backend ray \
            --pipeline-parallel-size 1 \
            --tensor-parallel-size 8 \
            --trust-remote-code
    fi
else
    echo "Starting WORKER number ${SLURM_PROCID}"
    ray start --address "$ip_head" --num-cpus "${SLURM_CPUS_PER_TASK}" --num-gpus $SLURM_GPUS_ON_NODE --block
fi
