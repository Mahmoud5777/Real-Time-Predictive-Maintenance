FILE: README_DEPLOYMENT.md
SOURCE: Lot4_Automation

=== SOURCE ORIGINAL ===
Lines: 67

=== MIGRATED VERSION ===
Lines: 67

=== DIFFERENCES ===

InputObject                                                                                                                   
-----------                                                                                                                   
1. DÃ©compresser `deployment\lot4\automation` Ã  la racine du dÃ©pÃ´t `Collaborative-Fog-Computing`.                          
   Get-ChildItem .\deployment\lot4\automation\*.ps1 | ForEach-Object {                                                        
   .\deployment\lot4\automation\Set-Lot4Config.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCI...
   .\deployment\lot4\automation\Install-Lot4.ps1 -Role central                                                                
   .\deployment\lot4\automation\Configure-Firewall.ps1 -Role central                                                          
   .\deployment\lot4\automation\Deploy-Lot4.ps1 -Role central                                                                 
   .\deployment\lot4\automation\Install-Lot4.ps1 -Role fog-a                                                                  
   .\deployment\lot4\automation\Configure-Firewall.ps1 -Role fog-a                                                            
   .\deployment\lot4\automation\Deploy-Lot4.ps1 -Role fog-a                                                                   
   .\deployment\lot4\automation\Register-FogNodes.ps1 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13          
   .\deployment\lot4\automation\Test-Lot4.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192...
.\\deployment\lot4\automation\\Configure-Monitoring.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -...
- Central : `.\deployment\lot4\automation\Stop-Lot4.ps1 -Role central`                                                        
- Chaque Fog : `.\deployment\lot4\automation\Stop-Lot4.ps1 -Role fog-a` (adapter le rÃ´le).                                   
1. DÃ©compresser `Lot4_Automation` Ã  la racine du dÃ©pÃ´t `Collaborative-Fog-Computing`.                                     
   Get-ChildItem .\Lot4_Automation\*.ps1 | ForEach-Object {                                                                   
   .\Lot4_Automation\Set-Lot4Config.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
   .\Lot4_Automation\Install-Lot4.ps1 -Role central                                                                           
   .\Lot4_Automation\Configure-Firewall.ps1 -Role central                                                                     
   .\Lot4_Automation\Deploy-Lot4.ps1 -Role central                                                                            
   .\Lot4_Automation\Install-Lot4.ps1 -Role fog-a                                                                             
   .\Lot4_Automation\Configure-Firewall.ps1 -Role fog-a                                                                       
   .\Lot4_Automation\Deploy-Lot4.ps1 -Role fog-a                                                                              
   .\Lot4_Automation\Register-FogNodes.ps1 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13                     
   .\Lot4_Automation\Test-Lot4.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13     
.\\Lot4_Automation\\Configure-Monitoring.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192....
- Central : `.\Lot4_Automation\Stop-Lot4.ps1 -Role central`                                                                   
- Chaque Fog : `.\Lot4_Automation\Stop-Lot4.ps1 -Role fog-a` (adapter le rÃ´le).                                              



