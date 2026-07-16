"""
Diagram-as-code source for architecture.png.

Regenerate with:
    python3 -m venv .venv && .venv/bin/pip install diagrams
    .venv/bin/python diagram/architecture.py
(requires the graphviz `dot` binary on PATH)
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import ALB, InternetGateway, CloudFront, Endpoint
from diagrams.aws.compute import ECS, ECR
from diagrams.aws.database import RDSPostgresqlInstance
from diagrams.aws.storage import S3
from diagrams.aws.devtools import Codepipeline, Codedeploy
from diagrams.aws.integration import Eventbridge
from diagrams.aws.security import SecretsManager, IAM
from diagrams.onprem.vcs import Github
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import Users

graph_attr = {
    "fontsize": "22",
    "bgcolor": "white",
    "pad": "0.6",
    "splines": "spline",
}

with Diagram(
    "Photo Uploader - AWS Architecture (eu-central-1)",
    filename="diagram/architecture",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    user = Users("End user")

    with Cluster("GitHub"):
        repo = Github("photouploader-app\n(main branch)")
        actions = GithubActions("GitHub Actions\n(OIDC, no long-lived keys)")
        repo >> actions

    with Cluster("AWS Account - eu-central-1"):

        oidc_role = IAM("GitHub Actions Role\n(OIDC trust)")
        ecr = ECR("ECR\nphotouploader repo")
        actions >> Edge(label="assume role via OIDC") >> oidc_role
        oidc_role >> Edge(label="push image (sha + latest)") >> ecr

        eventbridge = Eventbridge("EventBridge Rule\n(ECR image push)")
        pipeline = Codepipeline("CodePipeline\n(ECR + S3 sources)")
        codedeploy = Codedeploy("CodeDeploy\nBlue/Green")
        ecr >> Edge(label="triggers") >> eventbridge >> pipeline >> codedeploy

        with Cluster("VPC 10.0.0.0/16"):
            igw = InternetGateway("Internet Gateway")

            with Cluster("Public Subnets (2 AZs)"):
                alb = ALB("Application\nLoad Balancer")

            with Cluster("Private Subnets (2 AZs)"):
                with Cluster("ECS Fargate Service (1-4 tasks, CPU autoscaling)"):
                    ecs_service = ECS("photouploader-service\n(blue/green target groups)")
                rds = RDSPostgresqlInstance("RDS PostgreSQL\ndb.t3.micro")

                with Cluster("VPC Endpoints (no NAT Gateway)"):
                    vpce = Endpoint("S3 / ECR / Logs /\nSecrets Manager")

            igw >> alb
            alb >> Edge(label="HTTP :8080") >> ecs_service
            ecs_service >> Edge(label="JDBC :5432") >> rds
            ecs_service - Edge(style="dashed") - vpce

        secrets = SecretsManager("DB credentials")
        images_bucket = S3("S3 - private\nimages bucket")
        cdn = CloudFront("CloudFront\n(OAC, Price Class 200)")

        ecs_service >> Edge(label="read creds") >> secrets
        ecs_service >> Edge(label="PutObject") >> images_bucket
        images_bucket >> Edge(label="OAC (S3 blocks\ndirect access)") >> cdn

        codedeploy >> Edge(label="blue/green\ntraffic shift", style="bold", color="firebrick") >> ecs_service

    user >> Edge(label="HTTP") >> alb
    cdn >> Edge(label="HTTPS image URLs") >> user
