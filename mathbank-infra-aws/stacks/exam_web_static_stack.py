"""CDK stack: `mathbank-exam-web` as a static SPA on S3 + CloudFront (requirements/64 §9
continued). The first *static-frontend* hosting pattern in this repo — every other
stack here is a Lambda container image; this one is a plain Vite/React build (`dist/`)
with no server at all, so the cheapest/simplest fit is S3 (private, origin-access-control
only — no public bucket website hosting) behind a CloudFront distribution, not another
Lambda. (Doc 62's Amplify Hosting recommendation is for the repo's *Next.js* apps, which
need SSR; this SPA needs none.)

SPA client-side routing (`react-router-dom`'s `BrowserRouter`) means a path like
`/exam/<uuid>` has no matching S3 object — CloudFront's `error_responses` rewrites any
403/404 from the private S3 origin back to `/index.html` with an HTTP 200, letting the
React Router take over from there, rather than showing a dead S3 AccessDenied/NoSuchKey
page.
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE = "mathbank-exam-web"
DIST_DIR = REPO_ROOT / SERVICE / "dist"


class ExamWebStaticStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self, "ExamWebBucket",
            # Dev project, no versioning/retention needed — a redeploy just re-uploads
            # `dist/`; destroying the stack should leave nothing orphaned behind,
            # consistent with every other stack's "make destroy-one" cost story.
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

        distribution = cloudfront.Distribution(
            self, "ExamWebDistribution",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403, response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404, response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
            # Cheapest edge tier covering North America + Europe — a personal dev
            # project has no need for the priciest (all-edge-locations) tier.
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
        )

        if DIST_DIR.is_dir():
            s3deploy.BucketDeployment(
                self, "ExamWebDeployment",
                sources=[s3deploy.Source.asset(str(DIST_DIR))],
                destination_bucket=bucket,
                distribution=distribution,
                distribution_paths=["/*"],
            )

        self.distribution_domain = distribution.distribution_domain_name
        CfnOutput(self, "ExamWebUrl", value=f"https://{distribution.distribution_domain_name}")
