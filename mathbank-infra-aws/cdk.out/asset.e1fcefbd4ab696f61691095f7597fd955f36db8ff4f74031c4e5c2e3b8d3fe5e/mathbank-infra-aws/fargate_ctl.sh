#!/usr/bin/env bash
# Start/stop/status for one Fargate app (requirements/62 §5/§6, revised): every
# `ecs.FargateService` is created with desired_count=0 ("run only when needed"), no ALB
# — each running task gets its own public IP directly on its ENI, which changes on every
# start. This script flips desired_count and, for start/status, resolves that IP so you
# get a usable URL without digging through the console.
#
# Usage:
#   ./fargate_ctl.sh start  <mathbank-web|mathbank-live|mathbank-ml-frontend>
#   ./fargate_ctl.sh stop   <mathbank-web|mathbank-live|mathbank-ml-frontend>
#   ./fargate_ctl.sh status <mathbank-web|mathbank-live|mathbank-ml-frontend>
set -euo pipefail

ACTION="${1:?Usage: fargate_ctl.sh <start|stop|status> <mathbank-web|mathbank-live|mathbank-ml-frontend>}"
APP="${2:?Usage: fargate_ctl.sh <start|stop|status> <mathbank-web|mathbank-live|mathbank-ml-frontend>}"
REGION="${AWS_REGION:-us-east-2}"
PROFILE="${AWS_PROFILE:-aws-sutanu-admin}"
CLUSTER="mathbank-fargate-cluster"
STACK="MathBankFargateWebStack"

case "$APP" in
  mathbank-web) PORT=5173 ;;
  mathbank-live) PORT=5174 ;;
  mathbank-ml-frontend) PORT=5175 ;;
  *) echo "ERROR: unknown app '$APP' (expected mathbank-web, mathbank-live or mathbank-ml-frontend)" >&2; exit 1 ;;
esac

# CDK's generated CloudFormation output key for each app's ECS service short name, e.g.
# "mathbankwebServiceName" — the app's id with hyphens stripped, plus "ServiceName".
OUTPUT_KEY="$(echo "$APP" | tr -d '-')ServiceName"
SERVICE="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" --profile "$PROFILE" \
  --query "Stacks[0].Outputs[?OutputKey=='${OUTPUT_KEY}'].OutputValue | [0]" --output text 2>/dev/null || true)"
if [[ -z "$SERVICE" || "$SERVICE" == "None" ]]; then
  echo "ERROR: could not resolve ECS service name for $APP (output key $OUTPUT_KEY) — is $STACK deployed?" >&2
  exit 1
fi

aws_ecs() { aws ecs "$@" --cluster "$CLUSTER" --region "$REGION" --profile "$PROFILE"; }

resolve_public_ip() {
  # The ENI attachment can briefly lag just behind lastStatus flipping to RUNNING
  # (desiredStatus=RUNNING is set immediately on update-service, well before that) — retry
  # a few times rather than treating a transient empty/"None" value as fatal.
  local task_arn="$1"
  local eni_id="" public_ip=""
  for _ in $(seq 1 10); do
    eni_id="$(aws_ecs describe-tasks --tasks "$task_arn" \
      --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value | [0]" --output text)"
    if [[ -n "$eni_id" && "$eni_id" != "None" ]]; then
      public_ip="$(aws ec2 describe-network-interfaces --network-interface-ids "$eni_id" --region "$REGION" --profile "$PROFILE" \
        --query "NetworkInterfaces[0].Association.PublicIp" --output text 2>/dev/null || true)"
      [[ -n "$public_ip" && "$public_ip" != "None" ]] && break
    fi
    sleep 3
  done
  echo "$public_ip"
}

case "$ACTION" in
  start)
    echo "Starting $APP ($SERVICE)..."
    aws_ecs update-service --service "$SERVICE" --desired-count 1 >/dev/null
    echo "Waiting for the task to reach RUNNING (cold ECR pull + boot can take 30-90s)..."
    TASK_ARN=""
    for _ in $(seq 1 30); do
      TASK_ARN="$(aws_ecs list-tasks --service-name "$SERVICE" --query "taskArns[0]" --output text)"
      if [[ -n "$TASK_ARN" && "$TASK_ARN" != "None" ]]; then
        LAST_STATUS="$(aws_ecs describe-tasks --tasks "$TASK_ARN" --query "tasks[0].lastStatus" --output text)"
        [[ "$LAST_STATUS" == "RUNNING" ]] && break
      fi
      sleep 5
    done
    if [[ -z "$TASK_ARN" || "$TASK_ARN" == "None" || "${LAST_STATUS:-}" != "RUNNING" ]]; then
      echo "ERROR: no RUNNING task after 150s — check: aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION --profile $PROFILE" >&2
      exit 1
    fi
    PUBLIC_IP="$(resolve_public_ip "$TASK_ARN")"
    if [[ -z "$PUBLIC_IP" || "$PUBLIC_IP" == "None" ]]; then
      echo "ERROR: task is RUNNING but no public IP was assigned yet — re-run: ./fargate_ctl.sh status $APP" >&2
      exit 1
    fi
    echo "$APP is running: http://${PUBLIC_IP}:${PORT}"
    ;;
  stop)
    echo "Stopping $APP ($SERVICE)..."
    aws_ecs update-service --service "$SERVICE" --desired-count 0 >/dev/null
    echo "$APP desired-count set to 0 (billing stops once the running task drains, ~30s)."
    ;;
  status)
    aws_ecs describe-services --services "$SERVICE" \
      --query "services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}" --output table
    TASK_ARN="$(aws_ecs list-tasks --service-name "$SERVICE" --desired-status RUNNING --query "taskArns[0]" --output text)"
    if [[ -n "$TASK_ARN" && "$TASK_ARN" != "None" ]]; then
      PUBLIC_IP="$(resolve_public_ip "$TASK_ARN")"
      echo "URL: http://${PUBLIC_IP}:${PORT}"
    else
      echo "No running task."
    fi
    ;;
  *)
    echo "Usage: fargate_ctl.sh <start|stop|status> <mathbank-web|mathbank-live|mathbank-ml-frontend>" >&2
    exit 1
    ;;
esac
