function awsSaml --description 'aws saml login'
  set -l _account_id_arg $argv[1]
  set -l _iam_role_name $argv[2]
  set -l _saml_provider $argv[3]
  set -l _friendly_name $argv[4]

  set -l _aws_prefix "aws-cn"
  set -l _aws_region "cn-north-1"

  set -l _account_ids (string split , $_account_id_arg)

  for _account_id in $_account_ids
    set -l _saml_response (env AWS_DEFAULT_REGION=$_aws_region aws sts assume-role-with-saml \
      --role-arn arn:$_aws_prefix:iam::$_account_id:role/$_iam_role_name \
      --saml-assertion file:///tmp/saml.txt \
      --principal-arn arn:$_aws_prefix:iam::$_account_id:saml-provider/$_saml_provider)

    set -l _aws_access_key (echo "$_saml_response" | jq -r '.Credentials.AccessKeyId')
    set -l _aws_secret (echo "$_saml_response" | jq -r '.Credentials.SecretAccessKey')
    set -l _aws_token (echo "$_saml_response" | jq -r '.Credentials.SessionToken')

    sed -ie "/$_iam_role_name-$_friendly_name-$_account_id/,+6d" ~/.aws/config

    echo "[profile $_iam_role_name-$_friendly_name-$_account_id]
aws_access_key_id=$_aws_access_key
aws_secret_access_key=$_aws_secret
aws_session_token=$_aws_token
region=$_aws_region
output=json
" >> ~/.aws/config
  end
end
