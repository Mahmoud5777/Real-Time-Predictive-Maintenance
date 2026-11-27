CONFLICT 3
Source: C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing\Real-Time-Predictive-Maintenance\README.md
Target: C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing\projects\mp2\README.md

Source SHA256: FD639010D6F965E0A5709B16F5B0E7A68F553A03C89BFB5D87AAF8407F6892E6
Target SHA256: D876F0B6FD39D3B32F5C3CF4BE67471FF30969DB4C043162F267A0C799F5542A

git : warning: in the working copy of 'C:\Users\ayedi\Desktop\projets\Collaborative-Fog-Computing\projects\mp2\README.md', LF 
will be replaced by CRLF the next time Git touches it
Au caractère Ligne:34 : 21
+ ...          $Diff = git diff --no-index -- $SourceFile $Destination 2>&1
+                      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (warning: in the... Git touches it:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
diff --git "a/C:\\Users\\ayedi\\Desktop\\projets\\Collaborative-Fog-Computing\\Real-Time-Predictive-Maintenance\\README.md" "b/C:\\Users\\ayedi\\Desktop\\projets\\Collaborative-Fog-Computing\\projects\\mp2\\README.md"
index 3dde413..4df717d 100644
--- "a/C:\\Users\\ayedi\\Desktop\\projets\\Collaborative-Fog-Computing\\Real-Time-Predictive-Maintenance\\README.md"
+++ "b/C:\\Users\\ayedi\\Desktop\\projets\\Collaborative-Fog-Computing\\projects\\mp2\\README.md"
@@ -1,38 +1,11 @@
+# MP2 - Collaborative Fog Computing
 
-# Collaborative Fog Computing
+MP2 contains the scheduler, Fog A/B/C workers, MQTT adapters, shared models, and unit/integration tests.
 
-## Project Description
+See `docker-compose.yml` for the local service topology and `docker-compose.integrated.yml` for the MP1 integration variant. Review the relevant compose file and environment examples before starting services. LAN deployment instructions live under `deployment/lot4/core/`.
 
-A distributed Fog Computing architecture for
-industrial IoT monitoring and fault-tolerant
-dynamic task scheduling.
+Run tests from this directory after installing the module dependencies:
 
-## Main Components
-
-- Fog A: Production Zone A
-- Fog B: Production Zone B
-- Fog C: Production Zone C
-- Dynamic Scheduler
-- MQTT Communication
-- Resource Monitoring
-- Fault Tolerance and Recovery
-
-## Technologies
-
-- Python 3.12
-- FastAPI
-- MQTT / Mosquitto
-- Docker
-- Docker Compose
-- Prometheus
-- pytest
-
-## Project Structure
-
-- fog_nodes/: Independent Fog services
-- scheduler/: Dynamic task scheduling
-- shared/: Common data models
-- mqtt/: MQTT communication
-- tests/: Automated tests
-- monitoring/: Monitoring configuration
-- docs/: Technical documentation
+```powershell
+python -m pytest
+```
\ No newline at end of file
