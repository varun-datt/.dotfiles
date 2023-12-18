function azBastionVm --description 'start azure vm and bastion tunnel'
  set -l _vmArgs "--resource-group rg-samurailab-eaus-25 --name vmdevc250 --subscription fce8bb4e-480d-48c7-a9bb-ee2a861dabe2"
  set -l _powerState (eval "az vm get-instance-view $_vmArgs | jq -r '.instanceView.statuses[1].displayStatus'")
  if test $_powerState = 'VM deallocated'
    eval "az vm start $_vmArgs"
  end

  az network bastion tunnel --name "bas-samurailab-eaus-public-25" --resource-group "rg-samurailab-eaus-25" --target-resource-id "/subscriptions/fce8bb4e-480d-48c7-a9bb-ee2a861dabe2/resourceGroups/rg-samurailab-eaus-25/providers/Microsoft.Compute/virtualMachines/vmdevc250"  --resource-port 3389 --port 49160 $argv; 
end
