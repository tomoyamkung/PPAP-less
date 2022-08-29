# PPAP-less

## Advance preparation

### Install the AWS CLI

The installation method is optional. a Docker image is also acceptable.

```sh
➜  aws --version
aws-cli/2.4.29 Python/3.9.12 Darwin/19.6.0 source/x86_64 prompt/off
```

### Install the AWS SAM CLI

Install AWS SAM CLI referring to the following.

- https://docs.aws.amazon.com/ja_jp/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html

### Register a profile

Register a profile using credentials.csv of the AWS account where you want to deploy this program.
Specify the created profile as a parameter to the `sam` command.

## About template.yaml

1. Now that you have template.yaml.sample, copy it with the filename template.yaml
2. There are two "TBD" in template.yaml, so modify the contents to suit each environment

```sh
➜  cp template.yaml.sample template.yaml
➜  vim template.yaml
```

Next, Describe the contents of template.yaml.

```yaml
Parameters:
  ServiceName:
    Type: String
    Default: ppap-less
    MaxLength: 50
    MinLength: 5
```

The service name defaults to "ppap-less". It can be changed to any name.

```yaml
  IAMGroup:
    Type: AWS::IAM::Group
    Properties:
      GroupName: !Sub ${ServiceName}-group
      Policies:
        - PolicyName: !Sub ${ServiceName}-group-policy
          PolicyDocument:
            Version: 2012-10-17
            Statement:
              -
                Effect: Allow
                Action: s3:GetObject
                Resource: !Sub "arn:aws:s3:::${ServiceName}-bucket/*"
```

Create a group of IAM User; grant policy to see updated files in AWS S3.

```yaml
  IAMUser:
    Type: AWS::IAM::User
    Properties:
      UserName: !Sub ${ServiceName}-user
      Groups:
        - !Ref IAMGroup

  IAMUserAccessKey:
    Type: AWS::IAM::AccessKey
    Properties:
      UserName: !Ref IAMUser
    DependsOn: IAMUser

  IAMUserAccessKeySecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub ${IAMUser}-credentials
      SecretString: !Sub "{\"accessKeyId\":\"${IAMUserAccessKey}\",\"secretAccessKey\":\"${IAMUserAccessKey.SecretAccessKey}\"}"
    DependsOn: IAMUserAccessKey
```

Create an IAM User and an access key.
The created access key is registered in AWS Secrets Manager.

```yaml

  LambdaRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub ${ServiceName}-role
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          -
            Effect: Allow
            Action: sts:AssumeRole
            Principal:
              Service: lambda.amazonaws.com
      Policies:
        - PolicyName: !Sub ${ServiceName}-policy
          PolicyDocument:
            Version: 2012-10-17
            Statement:
              -
                Effect: Allow
                Action: secretsmanager:GetSecretValue
                Resource: !Sub arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:*
              -
                Effect: Allow
                Action:
                  - "logs:CreateLogGroup"
                  - "logs:CreateLogStream"
                  - "logs:PutLogEvents"
                Resource: !Sub "arn:aws:logs:${AWS::Region}:${AWS::AccountId}:*"
    DependsOn: IAMUserAccessKeySecret
```

Create a Lambda execution role. The following policies are granted.

- Authority to execute Lambda
- Authority to reference Secrets Manager
- Authority to create CloudWatch Logs groups and streams, and output logs

```yaml
  LambdaFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Environment:
        Variables:
          EXPIRE: 7  # TBD
          INCOMING_WEBHOOK_URL: https://xxx  # TBD
          SECRET: !Sub ${IAMUser}-credentials
      FunctionName: !Sub ${ServiceName}
      Handler: lambda_function.lambda_handler
      Role: !GetAtt LambdaRole.Arn
      Runtime: python3.9
      Timeout: 10
      MemorySize: 128
      Architectures:
        - x86_64
    Metadata:
      BuildMethod: makefile
    DependsOn:
      - LambdaRole
```

Create a AWS Lambda. Makefile is used for build.

EXPIRE" in TBD is the time limit for referencing files uploaded to AWS S3. The specification is up to 7 days.
Send the URL for viewing uploaded files to "INCOMING_WEBHOOK_URL", which should be a WebHook URL such as Slack or Google Chat.

```yaml
  S3Bucket:
    Type: AWS::S3::Bucket
    DeletionPolicy: Retain
    UpdateReplacePolicy: Retain
    Properties:
      BucketName: !Sub ${ServiceName}-bucket
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      LifecycleConfiguration:
        Rules:
          - Id: AutoDelete
            ExpirationInDays: 14
            Status: Enabled
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
```

Create an AWS S3 bucket with the following specifications

- DeletionPolicy: Do not delete bucket when a stack is deleted.
- UpdateReplacePolicy: Do not delete bucket when re-creating by CFn
- Encryption by AES256
- Uploaded files are automatically deleted after 14 days
- Enable Public Access Block

## Build, Deploy

Build the project.

```sh
➜  sam build
```

Next, deploy to AWS. The `--guided` option should be specified for the first deployment; the samconfig.toml file will be created, so you do not need to specify the `--guided` option for the second and subsequent deployments.

```sh
➜  sam deploy --profile PROFILE --guided  # first deployment
➜  sam deploy --profile PROFILE
```

## Trigger setting

Set up a trigger so that AWS Lambda is triggered when a file is uploaded to a bucket created in AWS S3. The main steps are as follows.

1. Log in to the AWS management console
2. Go to the AWS Lambda page created by CFn
3. Click the "Add trigger" button
4. "Select a source" should be "S3"
5. For "Bucket," select a bucket created with CFn.
6. "Event type", "Prefix", and "Suffix" are defaults.
7. Check the "Recursive Invocation" and click the "Add" button.

## Operation check

The procedure for checking operation is as follows

1. Upload files to the created AWS S3 bucket from the management console
2. Notifications are sent to the chat channel set in "INCOMING_WEBHOOK_URL"
3. Clicking on the URL will download the file
