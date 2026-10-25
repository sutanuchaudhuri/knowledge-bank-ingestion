"""Run after the isolated entrypoint synth; inspect no shared-stack templates."""
import json
import unittest
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


class SocraticTemplateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT / "cdk.out/MathBankSocraticStack.template.json").read_text()
        cls.resources = json.loads(cls.raw)["Resources"]

    def test_bounded_isolated_cognito_lambda(self):
        functions = [r["Properties"] for r in self.resources.values()
                     if r["Type"] == "AWS::Lambda::Function"
                     and r["Properties"].get("FunctionName") == "mathbank-socratic-api"]
        self.assertEqual(len(functions), 1)
        fn = functions[0]
        self.assertEqual(fn["MemorySize"], 512)
        self.assertEqual(fn["Timeout"], 30)
        self.assertNotIn("ReservedConcurrentExecutions", fn)
        env = fn["Environment"]["Variables"]
        self.assertEqual(env["SOCRATIC_AUTH_MODE"], "cognito")
        self.assertEqual(env["SOCRATIC_COOKIE_SECURE"], "true")
        self.assertEqual(env["SOCRATIC_AWS_PROFILE"], "")
        self.assertFalse(any(k.startswith("SOCRATIC_LOCAL") for k in env))
        self.assertFalse(any(k in env for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")))

    def test_no_secret_values_in_template_or_staged_asset(self):
        values = dotenv_values(ROOT.parent / "mathbank-rest/.env", interpolate=False)
        for key in ("POSTGRES_PASSWORD", "COGNITO_CLIENT_SECRET", "SOCRATIC_CSRF_SECRET"):
            self.assertTrue(values[key])
            self.assertNotIn(values[key], self.raw, msg=f"{key} leaked into template")
        for asset in (ROOT / "cdk.out").glob("asset.*"):
            if asset.is_dir():
                self.assertFalse(any(p.name == ".env" for p in asset.rglob(".env")))

    def test_scoped_iam_without_model_or_shared_service_privileges(self):
        for resource in self.resources.values():
            if resource["Type"] != "AWS::IAM::Policy":
                continue
            for statement in resource["Properties"]["PolicyDocument"]["Statement"]:
                actions = statement["Action"]
                actions = [actions] if isinstance(actions, str) else actions
                self.assertFalse(any(a.startswith(("bedrock:", "states:", "bedrock-agentcore:"))
                                     for a in actions))
                if any(a.startswith(("ssm:", "cognito-idp:")) for a in actions):
                    self.assertNotEqual(statement["Resource"], "*")
                    self.assertFalse(any(a.endswith("*") for a in actions))
        self.assertNotIn("MathBankRestStack", self.raw)


if __name__ == "__main__":
    unittest.main()
