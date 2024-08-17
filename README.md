Blurp
---

**SSRF all the things** 

<img src="images/logo.jpeg" alt="drawing" width="250"/>

---

Blurp is a simple site that diligently logs all incoming traffic for review. Useful for tracking SSRF callouts, etc.

This is currently live at: https://blurp.skelmis.co.nz

Some example requests:

![img.png](images/img.png)
![img_1.png](images/img_1.png)

##### Configuration

The following environment variables can be set to modify behaviour:
- `SERVING_DOMAIN`: A comma seperated string denoting expected hosts for this site
- `HIDE_QUERY_PARAMS`: Setting this to any value will hide query parameters on the home page
- `HIDE_URLS`: Setting this will hide URL's on the home page and instead only show timestamps
- Set both of the following to enforce a password when viewing request values:
  - `REQUEST_USERNAME`: The username for basic auth
  - `REQUEST_PASSWORD`: The password for basic auth