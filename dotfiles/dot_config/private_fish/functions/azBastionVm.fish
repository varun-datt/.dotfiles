function azBastionVm --description 'start azure vm and bastion tunnel ports'
  set -l _vmName $argv[1]
  set -l _resourceGroup $argv[2]
  set -l _subscription $argv[3]

  set -l _vmArgs "--resource-group $_resourceGroup --name $_vmName --subscription $_subscription"
  set -l _powerState (eval "az vm get-instance-view $_vmArgs | jq -r '.instanceView.statuses[1].displayStatus'")
  if test $_powerState = 'VM deallocated'
    eval "az vm start $_vmArgs"
  end

  set -l _bastionName (az network bastion list --resource-group $_resourceGroup --subscription $_subscription | jq -r 'last | .name')

  az network bastion tunnel \
    --name $_bastionName \
    --resource-group $_resourceGroup \
    --target-resource-id "/subscriptions/$_subscription/resourceGroups/$_resourceGroup/providers/Microsoft.Compute/virtualMachines/$_vmName" \
    --resource-port 3389 \
    --port 49160;
end
