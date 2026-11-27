# Same Dockerfile

Mermaid version of [03-build-push.png](03-build-push.png).

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
  df["same Dockerfile"]
  subgraph A["Docker / Podman"]
    direction LR
    a1["build<br/>+ push"]:::cream
    a2["plain<br/>image"]
    a3["general-<br/>purpose"]:::cream
    a1 --> a2 --> a3
  end
  subgraph B["datumctl"]
    direction LR
    b1["compute build<br/>--analyze"]:::cream
    b2["packaged<br/>image"]
    b3["unikernel or<br/>general-<br/>purpose"]:::good
    b1 --> b2 --> b3
  end
  df --> A
  df --> B
  A ~~~ B
  class df,a2 iwhite
  class b2 ilime
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

*Any image runs on general-purpose. `datumctl compute build` packages it for unikernel too.*
