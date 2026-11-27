# Lot 4 integration checklist

- [ ] Stable IP addresses / DHCP reservations for central + three Fog PCs
- [ ] Central MQTT reachable from Fog PCs (TCP 1883)
- [ ] Fog A/B/C have correct FOG_ID, zone and image
- [ ] Fog API ports reachable from central
- [ ] Scheduler FOG_A_URL / FOG_B_URL / FOG_C_URL updated to remote URLs
- [ ] Fog MQTT broker host set to central LAN IP
- [ ] Prometheus scrape targets changed from Docker DNS to remote IPs
- [ ] Grafana admin password stored in private env, not source control
- [ ] Firewall rules scoped to trusted LAN
- [ ] MP4 frontend can reach MP3 API central
- [ ] Central-only and Fog-only startup/stop tested
- [ ] Single LAN health/connectivity validation completed
- [ ] Mono-PC compose configuration retained for rollback
