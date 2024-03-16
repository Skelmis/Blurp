Blurp
---

*SSRF all the things*

A simple site that diligently logs all incoming traffic for review. Useful for tracking SSRF callouts, etc.

This is currently live at: https://blurp.skelmis.co.nz

Some example requests:

![img.png](images/img.png)
![img_1.png](images/img_1.png)

##### Configuration

The following environment variables can be set to modify behaviour:
- `HIDE_QUERY_PARAMS`: Setting this to any value will hide query parameters on the home page

Future features:
- Hiding query params in home page toggle
- Requiring auth to review requests