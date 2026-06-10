import boto3
import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List

@dataclass
class Finding:
    resource_id: str
    resource_type: str
    issue: str
    estimated_monthly_saving_usd: float
    region: str

@dataclass
class CostReport:
    generated_at: str
    account_id: str
    region: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def total_savings(self):
        return sum(f.estimated_monthly_saving_usd for f in self.findings)


def check_idle_ec2(ec2_client, cw_client, region) -> List[Finding]:
    findings = []
    paginator = ec2_client.get_paginator("describe_instances")
    
    for page in paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["running"]}]):
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                instance_id = instance["InstanceId"]
                instance_type = instance["InstanceType"]

                # Check avg CPU over last 7 days
                response = cw_client.get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName="CPUUtilization",
                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    StartTime=datetime.now(timezone.utc) - timedelta(days=7),
                    EndTime=datetime.now(timezone.utc),
                    Period=86400,
                    Statistics=["Average"]
                )

                if response["Datapoints"]:
                    avg_cpu = sum(d["Average"] for d in response["Datapoints"]) / len(response["Datapoints"])
                    if avg_cpu < 5.0:
                        findings.append(Finding(
                            resource_id=instance_id,
                            resource_type=f"EC2 ({instance_type})",
                            issue=f"Idle — avg CPU {avg_cpu:.1f}% over 7 days",
                            estimated_monthly_saving_usd=50.0,
                            region=region
                        ))

    return findings


def check_unattached_ebs(ec2_client, region) -> List[Finding]:
    findings = []
    paginator = ec2_client.get_paginator("describe_volumes")

    for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
        for volume in page["Volumes"]:
            size_gb = volume["Size"]
            volume_type = volume["VolumeType"]
            # gp3 ~$0.08/GB/month
            monthly_cost = size_gb * 0.08
            findings.append(Finding(
                resource_id=volume["VolumeId"],
                resource_type=f"EBS {volume_type} ({size_gb}GB)",
                issue="Unattached volume",
                estimated_monthly_saving_usd=monthly_cost,
                region=region
            ))

    return findings


def check_unused_elastic_ips(ec2_client, region) -> List[Finding]:
    findings = []
    response = ec2_client.describe_addresses()

    for address in response["Addresses"]:
        if "InstanceId" not in address and "NetworkInterfaceId" not in address:
            findings.append(Finding(
                resource_id=address.get("AllocationId", address.get("PublicIp")),
                resource_type="Elastic IP",
                issue="Unassociated Elastic IP ($3.65/month)",
                estimated_monthly_saving_usd=3.65,
                region=region
            ))

    return findings


def run_audit(region: str = "ap-south-1") -> CostReport:
    session = boto3.Session()
    ec2 = session.client("ec2", region_name=region)
    cw  = session.client("cloudwatch", region_name=region)
    sts = session.client("sts")

    account_id = sts.get_caller_identity()["Account"]
    report = CostReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        account_id=account_id,
        region=region
    )

    print(f"[*] Scanning account {account_id} in {region}...")

    print("[*] Checking idle EC2 instances...")
    report.findings.extend(check_idle_ec2(ec2, cw, region))

    print("[*] Checking unattached EBS volumes...")
    report.findings.extend(check_unattached_ebs(ec2, region))

    print("[*] Checking unused Elastic IPs...")
    report.findings.extend(check_unused_elastic_ips(ec2, region))

    return report


def print_report(report: CostReport):
    print("\n" + "="*70)
    print(f"  AWS COST OPTIMIZATION REPORT")
    print(f"  Account : {report.account_id}")
    print(f"  Region  : {report.region}")
    print(f"  Time    : {report.generated_at}")
    print("="*70)

    if not report.findings:
        print("\n  ✅ No cost optimization opportunities found.")
        return

    for f in report.findings:
        print(f"\n  ❗ {f.resource_type}")
        print(f"     ID      : {f.resource_id}")
        print(f"     Issue   : {f.issue}")
        print(f"     Saving  : ${f.estimated_monthly_saving_usd:.2f}/month")

    print("\n" + "-"*70)
    print(f"  💰 Total estimated monthly savings: ${report.total_savings:.2f}")
    print("="*70)

    with open("cost_report.json", "w") as fp:
        json.dump({
            "generated_at": report.generated_at,
            "account_id":   report.account_id,
            "region":       report.region,
            "total_savings_usd": report.total_savings,
            "findings": [vars(f) for f in report.findings]
        }, fp, indent=2)
    print("\n  Report saved to cost_report.json")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AWS Cost Optimizer")
    parser.add_argument("--region", default="ap-south-1")
    args = parser.parse_args()

    report = run_audit(region=args.region)
    print_report(report)