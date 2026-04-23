python scripts/build_docker.py --username syedahmed --tag v3.4  --torch-variant cpu
./build --runpod --username syedahmed --tag v3.4  --torch-variant cu121 --push

python scripts/build_docker.py --runpod --username syedahmed --push


docker run -it --rm \
-p 8188:8188 -p 8888:8888 -p 7860:7860 \
-e HF_TOKEN="<REDACTED_HF_TOKEN>" \
-e CIVITAI_TOKEN="dab15d421e0953c0fbab1430483fe88b" \
-v $(pwd)/workspace:/workspace syedahmed/comfyui-flux:v3.5-cpu



Round_Breasts_Slim_Waist
https://civitai.com/api/download/models/1782533?type=Model&format=SafeTensor

Hourglass_Body
https://civitai.com/api/download/models/1668530?type=Model&format=SafeTensor

Micro_Bikini
https://civitai.com/api/download/models/1857758?type=Model&format=SafeTensor

Jean_Shorts
https://civitai.com/api/download/models/817482?type=Model&format=SafeTensor

Round_Breasts_Slim_Waist_lora:
    type: file
    url: "https://civitai.com/api/download/models/1782533?type=Model&format=SafeTensor"
    destination: ComfyUI/models/loras/Round_Breasts_Slim_Waist_lora.safetensors
    description: "4x UltraSharp upscaling model"
    priority: low
    enabled: true

Hourglass_Body:
    type: file
    url: "https://civitai.com/api/download/models/1668530?type=Model&format=SafeTensor"
    destination: ComfyUI/models/loras/Hourglass_Body_lora.safetensors
    description: "Hourglass_Body"
    priority: low
    enabled: true

Micro_Bikini:
    type: file
    url: "https://civitai.com/api/download/models/1857758?type=Model&format=SafeTensor"
    destination: ComfyUI/models/loras/Micro_Bikini_lora.safetensors
    description: "Micro_Bikini"
    priority: low
    enabled: true

Jean_Shorts:
    type: file
    url: "https://civitai.com/api/download/models/817482?type=Model&format=SafeTensor"
    destination: ComfyUI/models/loras/Jean_Shorts_lora.safetensors
    description: "Jean_Shorts"
    priority: low
    enabled: true


    Wan2.1_14B_FusionX
    https://civitai.com/api/download/models/1882322?type=Model&format=SafeTensor&size=full&fp=fp8


Bouncy Walk - Wan I2V 14B
    https://civitai.com/models/1361346/bouncy-walk-wan-i2v-14b?modelVersionId=1537915

The Walk
https://civitai.com/api/download/models/1870675?type=Model&format=SafeTensor