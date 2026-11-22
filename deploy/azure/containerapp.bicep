// Optional Azure Container Apps deployment for the policy service (Phase 8).
// DOCS + IaC ONLY — never deployed by this repo. The owner runs it explicitly,
// with a budget alert set first, and deletes the resource group after.
// Region pinned to Germany West Central (EU data residency).

@description('Region — Germany West Central for EU data residency.')
param location string = 'germanywestcentral'

@description('Container image (GHCR), e.g. ghcr.io/<owner>/ai-semantic-guardrails-eu:v2.')
param image string

@description('Name prefix for the resources.')
param namePrefix string = 'guardrails-eu'

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: listKeys(logs.id, logs.apiVersion).primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-policy-service'
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: 'policy-service'
          image: image
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'ACA_PROFILE', value: 'oss' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/healthz', port: 8080 }
              initialDelaySeconds: 5
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
