# 베이스 이미지로 다운받은 오프라인용 PaddleOCR 이미지를 사용 (모델 가중치 포함)
FROM ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlepaddle/paddleocr-vl:latest-nvidia-gpu-offline

# JupyterLab 및 필수 구성 요소 설치
RUN pip install --no-cache-dir jupyterlab notebook

# 작업 디렉토리
WORKDIR /workspace

# 포트 개방
EXPOSE 8888

# 실행 명령어 (python -m 대신 jupyter lab을 직접 호출하되 경로 문제를 피하기 위해 아래와 같이 설정)
CMD ["/usr/local/bin/python3", "-m", "jupyterlab", "--ip=0.0.0.0", "--port=8888", "--allow-root", "--no-browser", "--ServerApp.token=''"]