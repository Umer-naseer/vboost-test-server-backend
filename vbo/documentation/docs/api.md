# API
 
Vboost Office provides a RESTful JSON-based API to communicate with mobile application and, possibly, external services.

The root API URL is [http://vboostoffice.com/api/v1/](http://vboostoffice.com/api/v1/).

> While logged into VBO, you can click this URL to get into the human-readable API interface. Every API request like [http://vboostoffice.com/api/v1/company](http://vboostoffice.com/api/v1/company) points to this interface by default. To get raw JSON data, one should use [http://vboostoffice.com/api/v1/company /?format=json](http://vboostoffice.com/api/v1/company/?format=json).

## Authentication

An API request is allowed only if:
 
 - it is made on behalf of an existing user
 - this user has the privilege to do this request (i.e., has *API user* group).

For mobile and command line clients, the API provides token-based authentication. Each user has a unique authentication token, and the client must ask for it providing the user's name and password. Example:
 
```plain
POST http://vboostoffice.com/api/v1/auth/login?login=LOGIN&password=PASSWORD&format=json
```

Response:

    {
        "auth_token": "TOKEN"
    }
   
Token is a string of 40 alphanumeric characters, unique per user. You can view the tokens at [Users](http://vboostoffice.com/auth/user) control panel.

Normally, token does not change. Hence, the client needs to request one only when logging into the system the first time. After a token is obtained, client may send actual API requests to obtain and send data, using **Authorization** header to send the token:

```plain
GET http://vboostoffice.com/api/v1/company HTTP 1.1
Authorization: Token TOKEN
```

Example for CURL:

```bash
$ curl 'http://vboostoffice.com/api/v1/company/?format=json' -H 'Authorization: Token TOKEN'
```

### User profile

To get current username and user data:

```plain
GET http://vboostoffice.com/api/v1/auth/me/?format=json
```

**Response:**

```
{
    "id": 1,
    "username": "USERNAME",
    "email": "username@example.org"
}
```

## Company

A user may have access to one only client company in VBO.

```plain
GET http://vboostoffice.com/api/v1/company/?format=json
```

```
{
    "id": 225,
    "name": "Bob Baker Toyota",
    "slug": "bob_baker_toyota",
    "key": "C1053",
    "status": "active",
    "logo": "http://vboostlive.com/media/companies/logo/Bob_Baker_Toyota_Logo.png",
    "terms": "Legal Terms and Conditions text..."
}
```

## Campaigns

Any company may have any number of campaigns. Example:

```plain
GET http://vboostoffice.com/api/v1/campaigns/?format=json
```
```
[
    {
        "company": 110,
        "name": "Cerritos Infiniti - My Ride",
        "key": "MR1001",
        "logo": "http://vboostlive.com/media/campaigns/110/110/logo/cinf-logo.png",
        "details": "Take good photos!",
        "color": "FF0000",
        "images": {
            "min_count": 1,
            "max_count": 7,
            "labels": [
                {
                    "name": "side",
                    "title": "Side",
                },
                {
                    "name": "front",
                    "title": "Front",
                }
            ]
        }
    }
]
```

Let's examine `images` field further.
 
### Campaign image parameters

In `images` field, you can see `min_count`, `max_count`, and `default_count` which are positive integers, `min_count` <= `default_count` <= `max_count`.

`labels` field defines visual labels for images. 

* `name` is a machine-readable slug field which will be used to submit the image with this label
* `title` is a human-readable title to label the image placeholder on mobile device.

## Contacts

A contact is usually a manager or sales representative responsible for creating and sending packages via mobile app to the server. Each contact is linked to a company. By API request, the user gets all contacts of all companies he or she has access to.
 
```plain
GET http://vboostoffice.com/api/v1/contacts/?format=json
```
```
[
    {
        "id": 771,
        "name": "John Doe",
        "is_active": true,
        "title": "",
        "type": "staff",
        "email": "john_doe@example.com",
        "phone": "123-456-7890",
        "photo": null,
        "company": 110
    },
    ...
]
```

### Create or change a contact

The `name` field is required.
 
```yaml
- POST http://vboostoffice.com/api/v1/contacts/?format=json
- Headers
  Authorization: Token TOKEN
- Data
  name=Jane Doe
```

Please note this is a schematic query. Example in CURL format:

```plain
curl -X POST 'http://vboostoffice.com/api/v1/contacts/?format=json' -H 'Authorization: Token TOKEN' --data 'name=Jane Doe'
```

This returns

```json
{
    "id":2436,
    "name":"Jane Doe",
    "is_active":true,
    "title":"",
    "type":"staff",
    "email":"",
    "phone":"",
    "photo":null,
    "company":110
}
```

Of course, you may supply other fields as well - email and phone, for example.

That is what you get if you create a contact that has the same name within the same company but is active:

```json
{
    "non_field_errors": ["This contact already exists in the database."],
    "is_active":"True",
    "id":"5593"
}
```

If this contact is deactivated:

```json
{
    "non_field_errors": ["This contact already exists in the database. Do you want to reactivate this contact?"],
    "is_active":"False",
    "id":"5593"
}
```

You can activate it to get this contact back working.

```plain
curl -X POST 'http://vboostoffice.com/api/v1/contacts/123/activate/?format=json' -H 'Authorization: Token TOKEN'
```

And, instead of deleting contacts, you need to deactivate them. Example to deactivate a contact:

```plain
curl -X POST 'http://vboostoffice.com/api/v1/contacts/123/deactivate/?format=json' -H 'Authorization: Token TOKEN'
```

Then, this contact won't show in the contact list anymore, but it exists. 

To change an existing and active contact:

```yaml
- PUT http://vboostoffice.com/api/v1/contacts/2436/?format=json
- Headers
  Authorization: Token TOKEN
- Data
  username=Mary Doe
```

Please note that HTTP method here is PUT, not POST.

## Packages

A package is a set of photos with some metadata, sent to Vboostoffice server as a whole. Here is a request.

```yaml
- POST http://vboostoffice.com/api/v1/packages/?format=json
- Headers
  Authorization: Token TOKEN
  Content-Type: application/x-form-urlencoded
- Data
  campaign=CAMPAIGN_ID
  contact=CONTACT_ID
  recipient_name=THE NAME OF CUSTOMER
  recipient_email=EMAIL
  recipient_phone=PHONE NUMBER
  recipient_permission=1 OR 0, WHETHER THE PERSON ALLOWS TO DISTRIBUTE MARKETING MATERIALS
  recipient_signature=BASE64 ENCODED IMAGE OF USER'S HAND-DRAWN SIGNATURE
  images=SEE BELOW
```

Campaign and contact are the required fields.

Images field is a text string in JSON format, written as follows:

```json
[{
    "image": "...",
    "name": "front"
}, {
    "image": "...",
    "name": "side",
}]
```

where images themselves are in JPEG, base64 encoded. Just like `recipient_signature`. Of course the string does not need to be nicely formatted, no indentation expected. Just valid JSON.

The number of images submitted must be between `min_count` and `max_count`. If the user submits an image not linked to a label, the mobile app may submit it with a numeric name (`4`, `5`, etc).

## Help page

Help page content is available at `http://vboostoffice.com/api/v1/help/`, no authorization required. 