# Same command, more places

Mermaid version of [02-many-places.png](02-many-places.png).

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
    fontSize: "22px"
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
  cmd["one command<br/>datumctl compute deploy"]:::cream
  wl["one Workload"]:::cream
  subgraph R[" "]
    direction LR
    i1["Dallas"]
    i2["Ashburn"]
    i3["San Jose"]
  end
  url["one HTTPS URL"]
  cmd --> wl
  wl --> i1 & i2 & i3
  i1 & i2 & i3 --> url
  class i1,i2,i3 ilime
  class url inavy
  style R fill:none,stroke:none
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

*One command, one Workload, one Instance in each city, one URL.*
