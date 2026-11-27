# Same command

Mermaid version of [01-same-command.png](01-same-command.png).

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
  subgraph DK["Docker"]
    direction LR
    dc["docker run<br/>-d -p 8080:80"]:::cream
    dp["a host port<br/>:8080"]
    dx["container<br/>on your host"]
    dc --> dp --> dx
  end
  subgraph DT["Datum"]
    direction LR
    tc["datumctl<br/>compute deploy"]:::cream
    tu["an HTTPS URL"]
    ti["Instance in a<br/>Datum region"]
    tc --> tu --> ti
  end
  DK ~~~ DT
  class dp,dx iwhite
  class tu inavy
  class ti ilime
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

*Same image, same port. A URL takes the place of the host port.*
