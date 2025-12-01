# case showing
### Powerful ComfyUI 
Firstly, you can follow up [ComfyUI Linux Installation](https://docs.comfy.org/installation/manual_install#linux) manuacript. Once you have installed ComfyUI.

Then。。。

安装好的 ComfyUI，可以通过下面脚本暴露出去，这样才能远程ip访问,0.0.0.0让这个服务不只绑定在 127.0.0.1上，而是接受多有网卡的请求

```bash
# 官方的安装步骤，最新参考上面链接地址
conda create -n comfyenv
conda activate comfyenv
git clone git@github.com:comfyanonymous/ComfyUI.git

conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia

# pip install torch==2.3.0+cu121 torchvision==0.18.0+cu121 torchaudio==2.3.0 --index-url https://download.pytorch.org/whl/cu121

# 防止 上面 conda dynamic 引用，更新了mkl底层依赖，导致“libtorch_cpu.so: undefined symbol: iJIT_NotifyEvent”报错
conda install "mkl<=2024.0.0" "intel-openmp<=2024.0.0" -c defaults -y

cd ComfyUI
pip install -r requirements.txt

python main.py --listen 0.0.0.0 --port 8188 

```

Tips:
补充一下可能遇到的 pytroch版本依赖问题，如果是按照 conda 安装的话，可能在使用 torch 的时候，报出如下错误
Errors: torch/lib/libtorch_cpu.so: undefined symbol: iJIT_NotifyEvent
解决办法：参考https://github.com/pytorch/pytorch/issues/123097#issuecomment-2055236551，可以降级
```bash
conda install "mkl<=2024.0.0" "intel-openmp<=2024.0.0" -c defaults -y
```

### Customized T2I Pipline
 
comming soon...