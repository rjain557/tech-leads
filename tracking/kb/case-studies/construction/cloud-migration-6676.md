# IT Infrastructure Modernization and Server Migration for the contractor

- **Industry:** Construction
- **Service theme:** cloud-migration
- **Engagement date:** 2025-01-13
- **Estimated effort:** 89 hrs (1236: 85h, 1232: 4h)

## Client context

The contractor aims to modernize its IT infrastructure by integrating with Azure, updating workstations for Azure login, migrating the on-premise domain controller to the Technijian datacen

## Scope of work

### Sync On-Premise Domain Controller to Azure

**Problem / context:**

This phase involves configuring and synchronizing the on-premise domain controller with Azure Active Directory (AD) to enable seamless integration and improved management capabilities.

**Strategy:**

Install and configure Azure AD Connect.Set up synchronization rules and schedules.Test synchronization and resolve any conflicts.

**Objectives:**

Establish a secure connection between the on-premise domain controller and Azure AD.Ensure continuous synchronization of user identities.

**General requirements:**

Azure AD subscription.On-premise domain controller credentials and access.

**Technical requirements:**

Installation of Azure AD Connect on the on-premise domain controller.Configuration of synchronization settings.

**Reporting & monitoring:**

Weekly status reports during implementation.Monitoring logs to ensure synchronization success.

**Assumptions:**

The existing on-premise domain controller is operational and has internet connectivity.Azure AD Connect tool will be used for synchronization.

**Success criteria:**

Successful synchronization of user identities between on-premise and Azure AD.

### Migrate Domain Controller to Technijian Datacenter

**Problem / context:**

Migrate the on-premise domain controller to the Technijian datacenter to enhance reliability and scalability.

**Strategy:**

Backup existing domain controller.Transfer data to the Technijian datacenter.Configure and test the new domain controller setup.

**Objectives:**

Seamless migration with minimal downtime.Ensure all services are operational post-migration.

**General requirements:**

Secure transfer protocol for migration.Configuration details of the Technijian datacenter.

**Technical requirements:**

Setup of the domain controller in the Technijian datacenter.Migration of data and services.

**Reporting & monitoring:**

Migration progress updates every few hours.Post-migration performance monitoring.

**Assumptions:**

Technijian datacenter is ready to host the domain controller.Backup of the domain controller is available.

**Success criteria:**

Domain controller fully functional in the Technijian datacenter.

### Decommission DC03, DC04, FS01, and TCM01

**Problem / context:**

Decommission obsolete servers DC03, DC04, FS01, and TCM01 following the successful migration of services.

**Strategy:**

Verify all data and services have been migrated.Safely decommission each server.Document the decommissioning process.

**Objectives:**

Remove obsolete servers without impacting current operations.Dispose of hardware following best practices.

**General requirements:**

Documentation of services running on these servers.

**Technical requirements:**

Safe data transfer protocols.Procedures for decommissioning hardware.

**Reporting & monitoring:**

Final report on decommissioned servers.

**Assumptions:**

All services have been successfully migrated.

**Success criteria:**

Confirmation that all servers have been decommissioned without issues.

## Outreach-ready summary

The contractor aims to modernize its IT infrastructure by integrating with Azure, updating workstations for Azure login, migrating the on-premise domain controller to the Technijian datacen
