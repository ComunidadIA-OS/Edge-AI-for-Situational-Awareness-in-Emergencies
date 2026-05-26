# XHeimdall SageMaker Training Container
# Thermal fire detection — YOLO26m fine-tuning
#
# Build: docker build --platform linux/amd64 -t xheimdall-training:latest -f docker/Dockerfile .
# Push:  docker tag xheimdall-training:latest {ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/xheimdall-training:latest
#        docker push {ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/xheimdall-training:latest

FROM ultralytics/ultralytics:8.4.53

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    sagemaker-training==4.7.0 \
    boto3 \
    imagecodecs \
    scikit-learn \
    opencv-python-headless \
    pyflir \
    pyyaml \
    wandb==0.16.6

COPY vision/training/train_sagemaker.py /opt/ml/code/train.py

ENV SAGEMAKER_PROGRAM=train.py

WORKDIR /opt/ml/code

ENTRYPOINT ["python", "/opt/ml/code/train.py"]
