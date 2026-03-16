#!/bin/bash
set -eu

FUNCTION_NAME="proposal-sqs-handler"
FUNCTION_PACKAGE="/opt/code/lambda/proposal_sqs_handler.zip"
QUEUE_NAME="proposal-processing-queue"
ARTIFACT_BUCKET="lambda-artifacts"
ARTIFACT_KEY="proposal_sqs_handler.zip"

echo "Criando Lambda do processamento de propostas..."

if [ ! -f "$FUNCTION_PACKAGE" ]; then
  echo "Pacote da Lambda não encontrado em $FUNCTION_PACKAGE"
  exit 1
fi

if ! awslocal s3api head-bucket --bucket "$ARTIFACT_BUCKET" >/dev/null 2>&1; then
  awslocal s3 mb "s3://$ARTIFACT_BUCKET"
fi

awslocal s3 cp "$FUNCTION_PACKAGE" "s3://$ARTIFACT_BUCKET/$ARTIFACT_KEY"

if ! awslocal lambda get-function --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
  awslocal lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --handler app.lambdas.proposal_sqs_handler.handler \
    --timeout 60 \
    --memory-size 512 \
    --code "S3Bucket=$ARTIFACT_BUCKET,S3Key=$ARTIFACT_KEY" \
    --environment "Variables={DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/teste_tecnico,MOCK_BANK_BASE_URL=http://mock-bank:8001,WEBHOOK_CALLBACK_BASE_URL=http://host.docker.internal:8000,AWS_ENDPOINT_URL=http://localstack:4566,AWS_REGION=us-east-1,AWS_ACCESS_KEY_ID=test,AWS_SECRET_ACCESS_KEY=test,SQS_QUEUE_NAME=proposal-processing-queue}"
else
  echo "Lambda $FUNCTION_NAME já existe, pulando criação."
fi

awslocal lambda wait function-active-v2 --function-name "$FUNCTION_NAME"

QUEUE_URL="$(awslocal sqs get-queue-url --queue-name "$QUEUE_NAME" --query 'QueueUrl' --output text)"
QUEUE_ARN="$(awslocal sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"

if ! awslocal lambda list-event-source-mappings --function-name "$FUNCTION_NAME" | grep -q "$QUEUE_ARN"; then
  awslocal lambda create-event-source-mapping \
    --function-name "$FUNCTION_NAME" \
    --batch-size 1 \
    --event-source-arn "$QUEUE_ARN"
else
  echo "Event source mapping para $QUEUE_ARN já existe, pulando criação."
fi

echo "Lambda e event source mapping configurados com sucesso!"
