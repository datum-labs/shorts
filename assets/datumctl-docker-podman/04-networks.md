# Same(-ish) IPv6 networks

Mermaid version of [04-networks.png](04-networks.png).

```mermaid
---
config:
  theme: base
  flowchart:
    wrappingWidth: 300
    padding: 10
    subGraphTitleMargin:
      top: 8
      bottom: 14
  themeVariables:
    fontFamily: "DejaVu Sans, Verdana, sans-serif"
    fontSize: "16px"
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
  subgraph DK["Docker: one host"]
    direction LR
    subgraph N1["one bridge network"]
      direction LR
      c1["web"]
      c2["api"]
      c1 -->|"name"| c2
    end
    subgraph N2["second"]
      c3["db"]
    end
    N1 -.-x|"isolated"| N2
  end
  subgraph DT["Datum: many regions"]
    direction LR
    subgraph M1["one network"]
      direction LR
      i1["web<br/>us-east-1"]
      i2["api<br/>us-central-1"]
      i1 -->|"name"| i2
    end
    subgraph M2["second"]
      i3["db"]
    end
    M1 -.-x|"isolated"| M2
  end
  DK ~~~ DT
  class c1,c2,c3 iwhite
  class i1,i2,i3 ilime
  classDef navy fill:#0C1D31,stroke:#0C1D31,color:#F6F5F1
  classDef pink fill:#EBCFD2,stroke:#B5605E,color:#0C1D31
  classDef lime fill:#E6F59B,stroke:#7C8A2E,color:#0C1D31
  classDef cream fill:#F6F5F1,stroke:#8A8E99,color:#0C1D31
  classDef bad fill:#F7D4D2,stroke:#B5605E,color:#7A1F1A,stroke-width:2px
  classDef good fill:#E6F59B,stroke:#5E6B1E,color:#0C1D31,stroke-width:2px
  classDef inavy fill:#0C1D31,stroke:#E6F59B,color:#0C1D31
  classDef ipink fill:#EBCFD2,stroke:#B5605E,color:#0C1D31
  classDef ilime fill:#E6F59B,stroke:#0C1D31,color:#0C1D31
  classDef iwhite fill:#FFFFFF,stroke:#0C1D31,color:#0C1D31
```

*Names resolve inside a network, and networks stay isolated. Datum's networks span regions. IPv4-only services are reachable by name, through DNS64 and NAT64.*
