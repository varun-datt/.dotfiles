function awsSaml --description 'aws saml login'
  set -l _account $argv[1]
  set -l _iam_role $argv[2]
  set -l _saml_provider $argv[3]

  set -l _aws_prefix "aws-cn"
  set -l _aws_region "cn-north-1"

  set -l _saml_response=$(env AWS_DEFAULT_REGION=$_aws_region aws sts assume-role-with-saml \
    --role-arn arn:$_aws_prefix:iam::$_account:role/$_iam_role \
    --saml-assertion file:///tmp/saml.txt \
    --principal-arn arn:$_aws_prefix:iam::$_account:saml-provider/$_saml_provider)
    # | jq -n --arg ACCESS_KEY_ID '.Credentials.AccessKeyId' 'aws_access_key_id=$ACCESS_KEY_ID'

  echo "$_saml_response"
end
