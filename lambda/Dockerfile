FROM python:3.12-slim

RUN python -m pip install --upgrade pip

WORKDIR /workspace

ENTRYPOINT ["bash", "-lc", "rm -rf lambda/dist && mkdir -p lambda/dist && python -m pip install -r requirements-runtime.txt -t /tmp/lambda-deps && python scripts/package_lambda.py /tmp/lambda-deps lambda/dist/proposal_sqs_handler.zip"]
