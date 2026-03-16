#!/bin/bash
set -eu

echo "Criando filas SQS no LocalStack..."

# Dead Letter Queue (DLQ) para mensagens que falharam
awslocal sqs create-queue \
  --queue-name proposal-processing-dlq \
  --attributes '{
    "MessageRetentionPeriod": "604800"
  }'

DLQ_URL="$(awslocal sqs get-queue-url --queue-name proposal-processing-dlq --query 'QueueUrl' --output text)"
DLQ_ARN="$(awslocal sqs get-queue-attributes --queue-url "$DLQ_URL" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"

# Fila principal para processamento de propostas
awslocal sqs create-queue \
  --queue-name proposal-processing-queue \
  --attributes "{
    \"VisibilityTimeout\": \"60\",
    \"MessageRetentionPeriod\": \"86400\",
    \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"
  }"

echo "Filas criadas com sucesso!"
awslocal sqs list-queues
