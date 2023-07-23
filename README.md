# Securely Connecting to an AWS Redshift Cluster (not publicly accessible) in your VPC by using EC2 Instance Connect Endpoint over the Internet without the need of a VPN/Bastion host and SSH

This is a CDK project written in TypeScript that provisions a Redshift Cluster, EC2 Instance Connect Endpoint, CloudFormation Custom Resources/Lambda, IAM Roles/Policies, Security Groups, Route Tables, Private Subnets, and a VPC.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `cdk deploy`      deploy this stack to your default AWS account/region
* `cdk diff`        compare deployed stack with current state
* `cdk synth`       emits the synthesized CloudFormation template
