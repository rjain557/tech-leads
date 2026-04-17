# Server Replacement from Windows Server 2012 to Windows Server 2022 and Virtualization Migration from Hyper-V to ESXi

- **Industry:** Other
- **Service theme:** server-infrastructure
- **Engagement date:** 2024-06-19
- **Estimated effort:** 84 hrs (1232: 32h, 1236: 52h)

## Client context

<div class="OutlineElement Ltr SCXW24020175 BCX8" style="-webkit-user-drag:none;-webkit-tap-highlight-color:transparent;margin:0px;padding:0px;user-select:text;clear:both;cursor:text;overflow:visible;

## Scope of work

### Planning and Preparation

**Problem / context:**

Conduct a thorough assessment of the current server environment and develop a detailed migration plan including timelines and resource allocation.

**Objectives:**

Ensure all stakeholders are informed and agree on the migration plan. 

Identify potential risks and mitigation strategies.

### Installation of Loaner Server

**Problem / context:**

Install and configure the loaner server with ESXi onsite and verify connectivity and performance.

### Building and Migrating to New Servers

**Problem / context:**

Build new servers on the loaner ESXi server and migrate data and applications from the old servers to the new servers on the loaner server.

### Decommission Old Servers and Upgrade HV01

**Problem / context:**

Decommission old servers and prepare HV01 for the ESXi installation. Migrate VMs from HV01 to the loaner server.

### Upgrade HV02 and Finalize Migration

**Problem / context:**

Migrate remaining VMs from HV02 to HV01. Upgrade HV02 to ESXi and migrate VMs back for load balancing.

### Load Balancing and Removal of Loaner Server

**Problem / context:**

Ensure VMs are balanced between HV01 and HV02 for optimal performance. Remove the loaner server from the environment.

## Outreach-ready summary

<div class="OutlineElement Ltr SCXW24020175 BCX8" style="-webkit-user-drag:none;-webkit-tap-highlight-color:transparent;margin:0px;padding:0px;user-select:text;clear:both;cursor:text;overflow:visible;
