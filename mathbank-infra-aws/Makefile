PYTHON ?= .venv/bin/python3
CDK := npx -y aws-cdk
AWS_PROFILE ?= aws-sutanu-admin
AWS_REGION ?= us-east-2

.PHONY: install
install:                           ## Create the CDK venv and install aws-cdk-lib/boto3
	python3 -m venv .venv
	$(PYTHON) -m pip install --quiet --upgrade pip
	$(PYTHON) -m pip install --quiet -r requirements.txt

.PHONY: bootstrap
bootstrap:                         ## One-time: bootstrap this AWS account/region for CDK (safe to re-run)
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) $(CDK) bootstrap

.PHONY: seed-ssm
seed-ssm:                          ## Seed SSM SecureString secrets for one service: make seed-ssm SERVICE=mathbank-rest
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./seed_ssm.sh $(or $(SERVICE),mathbank-rest)

.PHONY: fargate-start
fargate-start:                     ## Start one Fargate app (desired_count 0->1) and print its URL: make fargate-start APP=mathbank-web
	@test -n "$(APP)" || (echo "Usage: make fargate-start APP=mathbank-web|mathbank-live|mathbank-ml-frontend" && exit 1)
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh start $(APP)

.PHONY: fargate-stop
fargate-stop:                      ## Stop one Fargate app (desired_count ->0, billing stops once it drains): make fargate-stop APP=mathbank-web
	@test -n "$(APP)" || (echo "Usage: make fargate-stop APP=mathbank-web|mathbank-live|mathbank-ml-frontend" && exit 1)
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh stop $(APP)

.PHONY: fargate-status
fargate-status:                    ## Show one Fargate app's task count + URL if running: make fargate-status APP=mathbank-web
	@test -n "$(APP)" || (echo "Usage: make fargate-status APP=mathbank-web|mathbank-live|mathbank-ml-frontend" && exit 1)
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh status $(APP)

.PHONY: fargate-web-start fargate-web-stop fargate-web-status
fargate-web-start:                 ## Start mathbank-web on Fargate and print its URL
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh start mathbank-web
fargate-web-stop:                  ## Stop mathbank-web on Fargate
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh stop mathbank-web
fargate-web-status:                ## Show mathbank-web's Fargate task count + URL if running
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh status mathbank-web

.PHONY: fargate-live-start fargate-live-stop fargate-live-status
fargate-live-start:                ## Start mathbank-live on Fargate and print its URL
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh start mathbank-live
fargate-live-stop:                 ## Stop mathbank-live on Fargate
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh stop mathbank-live
fargate-live-status:               ## Show mathbank-live's Fargate task count + URL if running
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh status mathbank-live

.PHONY: fargate-ml-frontend-start fargate-ml-frontend-stop fargate-ml-frontend-status
fargate-ml-frontend-start:         ## Start mathbank-ml-frontend on Fargate and print its URL
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh start mathbank-ml-frontend
fargate-ml-frontend-stop:          ## Stop mathbank-ml-frontend on Fargate
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh stop mathbank-ml-frontend
fargate-ml-frontend-status:        ## Show mathbank-ml-frontend's Fargate task count + URL if running
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./fargate_ctl.sh status mathbank-ml-frontend

.PHONY: clean-cdk-out
clean-cdk-out:                     ## Wipe cdk.out before synth/deploy (GOTCHAS.md #44 — a stale cdk.out can self-nest into any REPO_ROOT-context Docker asset, e.g. mathbank-rest's)
	rm -rf cdk.out

.PHONY: ensure-colima
ensure-colima:                     ## Internal prerequisite: starts colima only if it isn't already running (used by synth/deploy/diff so you never have to remember colima-start yourself)
	@COLIMA_HOME="/Volumes/External/colima-home" colima status >/dev/null 2>&1 || $(MAKE) colima-start

.PHONY: synth
synth: clean-cdk-out ensure-colima  ## Validate the CDK stacks without deploying (auto-starts colima/docker if needed)
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) CDK_DEFAULT_ACCOUNT=$$(aws sts get-caller-identity --profile $(AWS_PROFILE) --region $(AWS_REGION) --query Account --output text) CDK_DEFAULT_REGION=$(AWS_REGION) $(CDK) synth

.PHONY: deploy
deploy: clean-cdk-out ensure-colima  ## Build the container image(s) and deploy every stack (auto-starts colima/docker if needed); override STACKS=MathBankXStack to target one
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) CDK_DEFAULT_ACCOUNT=$$(aws sts get-caller-identity --profile $(AWS_PROFILE) --region $(AWS_REGION) --query Account --output text) CDK_DEFAULT_REGION=$(AWS_REGION) $(CDK) deploy $(or $(STACKS),--all) --require-approval never

.PHONY: diff
diff: clean-cdk-out ensure-colima   ## Show what `make deploy` would change, without deploying (auto-starts colima/docker if needed)
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) CDK_DEFAULT_ACCOUNT=$$(aws sts get-caller-identity --profile $(AWS_PROFILE) --region $(AWS_REGION) --query Account --output text) CDK_DEFAULT_REGION=$(AWS_REGION) $(CDK) diff $(or $(STACKS),--all)

.PHONY: destroy
destroy:                           ## Tear down every deployed stack (stops all AWS charges for this project)
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) CDK_DEFAULT_ACCOUNT=$$(aws sts get-caller-identity --profile $(AWS_PROFILE) --region $(AWS_REGION) --query Account --output text) CDK_DEFAULT_REGION=$(AWS_REGION) $(CDK) destroy --force --all

.PHONY: destroy-one
destroy-one:                       ## "Pause"/stop one service, freeing its ECR image storage + log group: make destroy-one STACK=MathBankManimStudioStack
	@test -n "$(STACK)" || (echo "Usage: make destroy-one STACK=MathBankXStack" && exit 1)
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) CDK_DEFAULT_ACCOUNT=$$(aws sts get-caller-identity --profile $(AWS_PROFILE) --region $(AWS_REGION) --query Account --output text) CDK_DEFAULT_REGION=$(AWS_REGION) $(CDK) destroy --force $(STACK)

.PHONY: outputs
outputs:                           ## Print every deployed stack's outputs (e.g. Function URLs); override STACK=MathBankXStack for just one
	@for s in $(or $(STACK),MathBankRestStack MathBankAgentStack MathBankMlInferenceStack MathBankMcpCompetitionsStack MathBankManimStudioStack MathBankExamAgentStack MathBankExamWebStack); do \
	  echo "=== $$s ==="; \
	  AWS_PROFILE=$(AWS_PROFILE) aws cloudformation describe-stacks --stack-name $$s --region $(AWS_REGION) --query "Stacks[0].Outputs" --output table 2>/dev/null \
	    || echo "  (not deployed)"; \
	done

.PHONY: colima-start
colima-start:                      ## Start the local Docker-compatible runtime (needed by synth/deploy); VM disk lives on the external drive (GOTCHAS.md #46)
	COLIMA_HOME="/Volumes/External/colima-home" colima start --cpu 4 --memory 8 --disk 60 --vm-type=vz --mount-type=virtiofs

.PHONY: colima-stop
colima-stop:                       ## Stop the local Docker-compatible runtime
	COLIMA_HOME="/Volumes/External/colima-home" colima stop
