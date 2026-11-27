## Important validation note

This bundle was authored from the Compose files, Scheduler config, Fog config, MQTT config, and Prometheus config pasted by the user. It has not been run through Docker Compose against the user's project. Check the Compose profiles, path resolution, and command interpolation before deploying on the four computers. The MQTT broker is currently anonymous; do not use it outside a trusted lab LAN or expose it to the Internet.
