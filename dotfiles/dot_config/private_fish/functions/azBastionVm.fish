function azBastionVm --description 'start azure vm and bastion tunnel'
  set -l _vmArgs "--resource-group <resource-group> --name <vm-name> --subscription <subscription-id>"
  set -l _powerState (eval "az vm get-instance-view $_vmArgs | jq -r '.instanceView.statuses[1].displayStatus'")
  if test $_powerState = 'VM deallocated'
    eval "az vm start $_vmArgs"
  end

  az network bastion tunnel --name "<bastion-name>" --resource-group "<resource-group>" --target-resource-id "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Compute/virtualMachines/<vm-name>"  --resource-port 3389 --port 49160 $argv; 
end
