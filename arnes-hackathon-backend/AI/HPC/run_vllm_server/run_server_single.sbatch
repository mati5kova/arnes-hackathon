#!/bin/bash
#SBATCH --job-name=vllm_server
#SBATCH --output=server_err.txt
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --time=4:00:00
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-task=4
#SBATCH --mem=0
#SBATCH --exclusive
#SBATCH --partition=boost_usr_prod

WORK_DIR=/leonardo_work/AIFAC_5C0_171

CONTAINER_DIR=$WORK_DIR/containers
TRANSFORMERS_VERSION=4.56.1
CONTAINER=$CONTAINER_DIR/deepspeed_vllm_${TRANSFORMERS_VERSION}.sif

MODELS_DIR=$WORK_DIR/models/hf_models
model_name=$1

SCRIPT_DIR=$WORK_DIR/scripts/run_vllm_server

head_node_ip=$(hostname --ip-address)
echo "Head node IP: $head_node_ip"
vllm_port_number=65535
SERVER_ADDR="http://${head_node_ip}:${vllm_port_number}/v1"

OUTPUT_FILE=$SCRIPT_DIR/logs/$model_name.txt
mkdir -p $(dirname $OUTPUT_FILE)

srun \
    --output=$OUTPUT_FILE \
    singularity exec \
    --nv \
    --bind $MODELS_DIR:/models,$SCRIPT_DIR:/script \
    --pwd /script \
    $CONTAINER \
    bash -c "\
    echo 'Server address: $SERVER_ADDR' && \
    source /.venv/bin/activate && \
    python3 -m vllm.entrypoints.openai.api_server \
        --model /models/${model_name} \
        --host "0.0.0.0" \
        --port ${vllm_port_number} \
        --pipeline-parallel-size 1 \
        --tensor-parallel-size ${SLURM_GPUS_ON_NODE}"
