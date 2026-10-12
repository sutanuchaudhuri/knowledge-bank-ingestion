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

.PHONY: clean-cdk-out
clean-cdk-out:                     ## Wipe cdk.out before synth/deploy (GOTCHAS.md #44 — a stale cdk.out can self-nest into any REPO_ROOT-context Docker asset, e.g. mathbank-rest's)
	rm -rf cdk.out

.PHONY: synth
synth: clean-cdk-out               ## Validate the CDK stacks without deploying (requires colima/docker running)
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) CDK_DEFAULT_ACCOUNT=$$(aws sts get-caller-identity --profile $(AWS_PROFILE) --region $(AWS_REGION) --query Account --output text) CDK_DEFAULT_REGION=$(AWS_REGION) $(CDK) synth

.PHONY: deploy
deploy: clean-cdk-out              ## Build the container image(s) and deploy every stack (requires colima/docker running); override STACKS=MathBankXStack to target one
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) CDK_DEFAULT_ACCOUNT=$$(aws sts get-caller-identity --profile $(AWS_PROFILE) --region $(AWS_REGION) --query Account --output text) CDK_DEFAULT_REGION=$(AWS_REGION) $(CDK) deploy $(or $(STACKS),--all) --require-approval never

.PHONY: diff
diff: clean-cdk-out                ## Show what `make deploy` would change, without deploying
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
	@for s in $(or $(STACK),MathBankRestStack MathBankAgentStack MathBankMlInferenceStack MathBankMcpCompetitionsStack MathBankManimStudioStack); do \
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
