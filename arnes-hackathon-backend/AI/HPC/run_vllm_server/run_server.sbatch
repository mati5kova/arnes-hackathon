#!/bin/bash
#SBATCH --job-name=vllm_server
#SBATCH --account=AIFAC_5C0_171
#SBATCH --output=server_err.txt
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=1
#SBATCH --time=0:30:00
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-task=4
#SBATCH --mem=0
#SBATCH --exclusive
#SBATCH --partition=boost_usr_prod
#SBATCH --qos=boost_qos_dbg

WORK_DIR=/leonardo_work/AIFAC_5C0_171

CONTAINER_DIR=$WORK_DIR/containers
CONTAINER_VERSION=qwen3_5
CONTAINER=$CONTAINER_DIR/vllm-openai_${CONTAINER_VERSION}.sif

MODELS_DIR=$WORK_DIR/models/hf_models
model_name=$1

SCRIPT_DIR=$WORK_DIR/scripts/run_vllm_server

nodes=$(scontrol show hostnames "$SLURM_JOB_NODELIST")
head_node=$(echo "$nodes" | head -n 1)
head_node_ip=$(srun --nodes=1 --ntasks=1 -w "$head_node" hostname --ip-address)
echo "Head node IP: $head_node_ip"

OUTPUT_FILE=$SCRIPT_DIR/logs/$model_name.txt
mkdir -p $(dirname $OUTPUT_FILE)

srun \
    --output=$OUTPUT_FILE \
    singularity exec \
    --nv \
    --bind $MODELS_DIR:/models,$SCRIPT_DIR:/script \
    --pwd /script \
    $CONTAINER \
    ./initialize_ray_and_start.sh $model_name $head_node_ip
