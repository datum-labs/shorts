# Same networks, IPv6 inside

Mermaid version of [04-networks.png](04-networks.png).

```mermaid
---
config:
  theme: base
  flowchart:
    wrappingWidth: 420
    padding: 14
    subGraphTitleMargin:
      top: 8
      bottom: 14
  themeVariables:
    fontFamily: "DejaVu Sans, Verdana, sans-serif"
    primaryColor: "#F6F5F1"
    primaryTextColor: "#0C1D31"
    primaryBorderColor: "#0C1D31"
    lineColor: "#2F3F48"
    clusterBkg: "#FBFAF7"
    clusterBorder: "#B9B5AC"
    labelBackground: "#F6F5F1"
    edgeLabelBackground: "#F6F5F1"
    mainBkg: "#F6F5F1"
---
flowchart TB
  subgraph DK["Docker, one host"]
    direction LR
    subgraph N1["network appnet"]
      direction LR
      c1["web"]:::white -->|"api, by name"| c2["api"]:::white
    end
    subgraph N2["network isonet"]
      c3["db"]:::white
    end
    N1 -.-x|"no route, no name"| N2
  end
  subgraph DT["Datum, every location"]
    direction LR
    subgraph M1["network default"]
      direction LR
      i1["web · IAD"]:::lime -->|"INSTANCE.instances.datum.internal"| i2["api · DFW"]:::lime
    end
    subgraph M2["network backend"]
      i3["db"]:::lime
    end
    net["Internet<br/>IPv6 direct<br/>IPv4 by name, via NAT64"]:::white
    M1 -.-x|"isolated"| M2
    M2 ~~~ net
  end
  DK ~~~ DT
  classDef navy fill:#0C1D31,stroke:#0C1D31,color:#F6F5F1
  classDef lime fill:#E6F59B,stroke:#7C8A2E,color:#0C1D31
  classDef white fill:#FFFFFF,stroke:#0C1D31,color:#0C1D31
  classDef cream fill:#F6F5F1,stroke:#8A8E99,color:#0C1D31
  classDef bad fill:#F7D4D2,stroke:#B5605E,color:#7A1F1A
  classDef good fill:#E6F59B,stroke:#5E6B1E,color:#0C1D31
```

*Names resolve inside a network, and networks stay isolated. Datum's networks span cities. IPv4-only services are reachable by name, through DNS64 and NAT64.*
