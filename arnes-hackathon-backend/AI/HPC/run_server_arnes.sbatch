#!/bin/bash

# run_server_arnes.sbatch  - vLLM strežnik na Arnes HPC
# original: run_server_single.sbatch (LEONARDO) (hvala Domen Vreš)

#SBATCH --job-name=vllm_server_tools                         # job mora imeti neko ime, potem vidno v npr `squeue -u $USER`
#SBATCH --output=server_log_%j.txt
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --time=12:00:00                                 # particija gpu dovoli do 4 dni (HH:MM:SS format!!)
#SBATCH --cpus-per-task=8                               # V100S vozlišča: AMD EPYC 7272
#SBATCH --mem=64G                                       # 12B model potrebuje cca 24 GB VRAM + RAM
#SBATCH --gres=gpu:2                                    # 2x GPU 
#SBATCH --partition=gpu                                 # treba dati tako


MODELS_DIR="$HOME/models"
model_name=${1:-"GaMS3-12B-Instruct"} # vzemi prvi argument ali pa tega defaultnega ki je trenutno edini potegnjen iz hugginfaca (mogoce probamo se 27B?)
VENV="$HOME/vllm_venv" # pot do virtualnega okolja z vLLM


head_node_ip=$(hostname --ip-address)
vllm_port_number=65535
echo "======================================================="
echo "Vozlišče   : $(hostname)"
echo "IP         : $head_node_ip"
echo "Model      : $model_name"
echo "Server URL : http://${head_node_ip}:${vllm_port_number}/v1"
echo "======================================================="

nvidia-smi
echo "-------------------------------------------------------"

# MODULI
module purge
module load Python/3.11
module load CUDA
echo "Python : $(python --version)"
echo "CUDA   : $(nvcc --version | grep release)"

#  virtualno okolje za vLLM, prvic se loada cca 5min potem pa se samo aktivira
if [ ! -d "$VENV" ]; then
    echo "Ustvarjam virtualno okolje in nameščam vLLM v $VENV ..."
    python -m venv "$VENV"
    source "$VENV/bin/activate"
    pip install --quiet vllm
else
    source "$VENV/bin/activate"
fi
echo "vLLM : $(python -c 'import vllm; print(vllm.__version__)')"
echo "-------------------------------------------------------"

# zagon streznika
# kaj se vbistu zgodi
# 1. nalozi model (.safetensors datoteke ki jih vidis na hugginfaceu) iz diska v RAM
# 2. prenese uteži v VRAM
# 3. zažene HTTP strežnik
python3 -m vllm.entrypoints.openai.api_server \
    --model "${MODELS_DIR}/${model_name}" \
    --host "0.0.0.0" \
    --port ${vllm_port_number} \
    --tensor-parallel-size 2 \
    --enable-auto-tool-choice \
    --tool-call-parser pythonic \
    --max-model-len 40816