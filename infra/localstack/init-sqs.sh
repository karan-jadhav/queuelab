#!/usr/bin/env bash
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
MAIN_QUEUE="queuelab-main"
DLQ_QUEUE="queuelab-dlq"
MAX_RECEIVE_COUNT="${QUEUELAB_SQS_MAX_RECEIVE_COUNT:-3}"
VISIBILITY_TIMEOUT="${QUEUELAB_SQS_VISIBILITY_TIMEOUT:-30}"

awslocal sqs create-queue \
  --region "${REGION}" \
  --queue-name "${DLQ_QUEUE}" >/dev/null

DLQ_URL="$(awslocal sqs get-queue-url \
  --region "${REGION}" \
  --queue-name "${DLQ_QUEUE}" \
  --query QueueUrl \
  --output text)"

DLQ_ARN="$(awslocal sqs get-queue-attributes \
  --region "${REGION}" \
  --queue-url "${DLQ_URL}" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' \
  --output text)"

REDRIVE_POLICY="$(printf '{"deadLetterTargetArn":"%s","maxReceiveCount":"%s"}' "${DLQ_ARN}" "${MAX_RECEIVE_COUNT}")"
ATTRIBUTES="$(printf '{"VisibilityTimeout":"%s","RedrivePolicy":"%s"}' "${VISIBILITY_TIMEOUT}" "${REDRIVE_POLICY//\"/\\\"}")"

awslocal sqs create-queue \
  --region "${REGION}" \
  --queue-name "${MAIN_QUEUE}" \
  --attributes "${ATTRIBUTES}" >/dev/null

echo "created SQS queues: ${MAIN_QUEUE}, ${DLQ_QUEUE}"
