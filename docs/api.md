# **PACER Case Locator (PCL) Application Programming Interface (API) User Guide**

**November 2024**

## **Contents**

| Overview                          | 4  |
|-----------------------------------|----|
| Public Environments               | 4  |
| Schema                            | 4  |
| Quick Start                       | 5  |
| PACER Authentication API          | 6  |
| Search Tools                      | 6  |
| Immediate Searches                | 6  |
| Case and Party Search Examples    | 9  |
| Immediate Searches                | 9  |
| Case Search – JSON                | 9  |
| Case Search – XML                 | 11 |
| Party Search - JSON               | 13 |
| Party Search - XML                | 17 |
| Advanced Searches                 | 21 |
| Batch Searches                    | 28 |
| Batch Search Examples             | 33 |
| Start a Batch Case Search - JSON  | 33 |
| Start Batch Case Search - XML     | 34 |
| Get Batch Job Status - JSON       | 34 |
| Get Batch Job Status - XML        | 35 |
| Get List of Batch Jobs – JSON     | 36 |
| Get List of Batch Jobs – XML      | 37 |
| Get Batch Job Results - JSON      | 38 |
| Get Batch Job Results - XML       | 38 |
| PCL Search API                    | 40 |
| Setting the Headers               | 40 |
| API Endpoints                     | 41 |
| Basic Searches                    | 41 |
| Batch Jobs                        | 41 |
| Search Criteria—Data Definitions  | 44 |
| Case Searches – Searchable Fields | 44 |

| Case Search – JSON Representation         | Case Search – XML Representation  | 47 |
|-------------------------------------------|-----------------------------------|----|
|                                           |                                   | 47 |
| Party Searches – Searchable Fields        |                                   | 48 |
| Party Search – JSON Representation        | Party Search – XML Representation | 52 |
| Search Results—Data Definitions           |                                   | 53 |
| Case Search Results                       |                                   | 53 |
| Party Search Results                      |                                   | 56 |
| Sorting                                   |                                   | 59 |
| Sortable Case Fields                      |                                   | 59 |
| Sortable Party Fields                     |                                   | 59 |
| Pagination                                |                                   | 59 |
| Appendix A: Court IDs                     |                                   | 60 |
| Appendix B: Bankruptcy Chapters           |                                   | 65 |
| Appendix C: Civil Nature of Suits         |                                   | 66 |
| Appendix D: Appellate Nature of Suits     |                                   | 69 |
| Appendix E: Search Regions in Production. |                                   | 76 |
| Appendix F: Case Types                    |                                   | 80 |
| Appendix G: Response Codes                |                                   | 81 |

## <span id="page-3-0"></span>Overview

The PACER Case Locator (PCL) is a nationwide index of federal court cases. The public PCL application programming interface (API) allows users to programmatically search the index for federal cases or associated parties. The PCL API is capable of the same search functionality as the PCL application and searches the same data set.

The PCL API is organized around representational state transfer (REST) with simple and intuitive URLs. All services use standard HTTP verbs and response codes and use either XML or JSON encoding for requests and responses.

## <span id="page-3-1"></span>Public Environments

A valid PACER account is required to use the PCL API. Register for a Production PACER account at [https://pacer.uscourts.gov.](https://pacer.uscourts.gov/) All searches in the Production environment are billable. For more information about charges, visit the [PACER Pricing page.](https://pacer.uscourts.gov/pacer-pricing-how-fees-work)

For API testing, a separate PACER QA environment is available. This environment contains a subset of test PCL data, and searches are not billable. To access this environment, a QA PACER account is required. This account is separate from any other PACER accounts and can only be used in the QA environment. Register for this type of account at: [https://qa-pacer.uscourts.gov.](https://qa-pacer.uscourts.gov/)

The PCL API has different endpoints for QA and Production. Use a QA account to access the QA environment, and use a live PACER account to access the Production environment.

The table below contains the URLs and URL name that is used throughout the document. The URL name in the examples indicates a URL for either environment. The user should substitute the appropriate URL for the selected environment.

The production environment is not available during the public testing period, it will become available when the PCL API is released.

| URL Purpose          | URL Name          | QA URL                | Production URL           |
|----------------------|-------------------|-----------------------|--------------------------|
| Account registration | registrationurl   | qa-pacer.uscourts.gov | pacer.uscourts.gov       |
| Authentication       | authenticationurl | qa-login.uscourts.gov | pacer.login.uscourts.gov |
| PCL API              | pclapiurl         | qa-pcl.uscourts.gov   | pcl.uscourts.gov         |

#### <span id="page-3-2"></span>**Schema**

XML documents represent the XML schema definitions (XSDs) used for all client requests. Reference these files to understand the different request and response types, and what elements compose them. Download the XSDs on the Developer Resources page of [pacer.uscourts.gov.](https://pacer.uscourts.gov/)

## <span id="page-4-0"></span>Quick Start

This section provides a brief introduction to each of the PCL APIs, their recommended usage, and their expected output. For a detailed description of each PCL API, please see the relevant API section below. **NOTE:** This section will provide code snippets in Java.

In general, the PCL APIs are divided into two broad groups: authentication and search tools. Within the search tools gbatchroup, there are two more API groups: immediate search results and batch searches. And each of those groups includes two or more functions.

![](_page_4_Figure_3.jpeg)

## <span id="page-5-0"></span>PACER Authentication API

To access a PACER system, the first step is to get an authentication token using your PACER username and password. The PACER Authentication API provides a way for the user to authenticate with PACER automatically and without a user interface. This can help facilitate access for automated systems.

**NOTE:** For further details on PACER authentication, see the [PACER](https://pacer.uscourts.gov/help/pacer/pacer-authentication-api-user-guide)  [Authentication API User Guide](https://pacer.uscourts.gov/help/pacer/pacer-authentication-api-user-guide) for examples, common error messages and solutions, and more.

The first step in using the PCL API is to get an authentication token using your PACER username and password. If you do not have a PACER account, you may register for one at the appropriate account registration URL (see Public Environments section). The PACER authentication service accepts a valid PACER username and password and returns an authentication token.

The authentication token is required for all PCL API requests. This authentication token should be presented in the HTTP request header of each search as the header X-NEXT-GEN-CSO.

**NOTE:** These headers are specific to the PCL API and differ slightly from the values noted in the PACER authentication API.

The authentication service call is valid for a set period of time and should be used until it expires. Do not call the authentication service for every PCL search.

#### <span id="page-5-1"></span>**Search Tools**

As noted above, the search tools API is broadly composed of two groups: those that return results immediately and those that batch results for later download.

Immediate searches return results in groups of 54. Each group of immediate search results is referred to as a "page." The maximum search result size for an immediate search is 5,400 items (cases or parties) or 100 pages. In contrast, batch searches return a single batch of results with the maximum number of search results limited to 108,000 items (cases or parties) or 2,000 pages.

#### <span id="page-5-2"></span>Immediate Searches

There are two types of immediate searches: case search and party search. Case searches return groups of cases, and party searches return groups of parties to cases. This section reviews these searches, while later sections provide additional details of their use and search parameters.

Each API accepts the search criteria in either XML or JSON formats. The JSON format will be used for the examples below.

#### Immediate Case Search

The immediate case search API accepts criteria that describe desired cases. Example search criteria include case number, case title, and date filed. The full descriptions of the available case search criteria are available in the [Search Criteria](#page-43-0) section, below.

```
HttpURLConnection conn = null;
try {
 URL url = new URL("https://qa-pcl.uscourts.gov/pcl-public-api/rest" + 
 "/cases/find?page=0");
 conn = (HttpURLConnection) url.openConnection();
 conn.setDoOutput(true);
 conn.setRequestMethod("POST");
 conn.setRequestProperty("Content-Type", "application/json");
 conn.setRequestProperty("Accept", "application/xml");
 conn.setRequestProperty("X-NEXT-GEN-CSO", nextGenCsoKey);
 // will find cases with titles starting with "Jacob", including Jacobs, 
 // Jacobson, Jacoby, etc.
 String searchBody = "{ \"caseTitle\": \"Jacob\" }";
 OutputStream os = conn.getOutputStream();
 os.write(searchBody.getBytes());
 os.flush();
 InputStreamReader isr = new InputStreamReader((conn.getInputStream()));
 // stream search results into a BufferedReader
 BufferedReader br = new BufferedReader(isr);
 //-------------------------------------------------------------------------
 // Check for a new NextGenCso Key 
 //-------------------------------------------------------------------------
 Map<String, List<String>> responseHeaderFields = conn.getHeaderFields();
 if (responseHeaderFields.containsKey("X-NEXT-GEN-CSO")) {
 List<String> nextGenCsoResponse = responseHeaderFields.get("X-NEXT-GEN-CSO");
 if ((nextGenCsoResponse != null) && (nextGenCsoResponse.size() > 0)) {
 String newNextGenCso = nextGenCsoResponse.get(0);
 System.out.printf("New NextGenCSO Key: %s\n", newNextGenCso);
 }
 }
 //-------------------------------------------------------------------------
 // Process Response from Server
 //-------------------------------------------------------------------------
 String responseLine;
 StringBuilder requestResponse = new StringBuilder();
 while ((responseLine = reader.readLine()) != null) {
 requestResponse.append(responseLine);
 }
}
catch (IOException e) {
 // NOTE that an IOException with HTTP response code 401 means that an invalid
 // or expired NextGenCSO key was provided and 406 means that an invalid
 // search parameter was provided.
 e.printStackTrace();
 System.exit(-1);
}
finally {
 if (conn != null) {
 conn.disconnect();
 }
}
```

#### Immediate Party Search

The immediate party search API accepts criteria that describe desired parties. Example search criteria include case number, party name, and party type. The full descriptions of the available party search criteria are available in the [Search Criteria](#page-43-0) section below.

```
HttpURLConnection conn = null;
try {
 URL url = new URL("https://qa-pcl.uscourts.gov/pcl-public-api/rest" + 
 "/parties/find?page=0");
 conn = (HttpURLConnection) url.openConnection();
 conn.setDoOutput(true);
 conn.setRequestMethod("POST");
 conn.setRequestProperty("Content-Type", "application/json");
 conn.setRequestProperty("Accept", "application/xml");
 conn.setRequestProperty("X-NEXT-GEN-CSO", nextGenCsoKey);
 // search for all parties with last names starting with 'Smith' in cases
 // filed on or after January 1, 2010.
 String searchBody = "{ \"lastName\": \"Smith\", " +
 " \"courtCase\": { " +
 " \"dateFiledFrom\": \"2010-01-01\" } }";
 OutputStream os = conn.getOutputStream();
 os.write(searchBody.getBytes());
 os.flush();
 InputStreamReader isr = new InputStreamReader((conn.getInputStream()));
 // stream search results into a BufferedReader
 BufferedReader br = new BufferedReader(isr);
 // Process results similarly to Case Search, including checking for new key
}
catch (IOException e) {
 // NOTE that an IOException with HTTP response code 401 means that an invalid
 // or expired NextGenCSO key was provided and 406 means that an invalid
 // search parameter was provided.
 e.printStackTrace();
 System.exit(-1);
}
finally {
 if (conn != null) {
 conn.disconnect();
 }
}
```

Example: Immediate party search

#### <span id="page-8-0"></span>**Case and Party Search Examples**

Sample search responses are included in the first examples but not in subsequent examples. The X-NEXT-GEN-CSO authentication token must be included in the header of each API request. The same authentication token is valid for a certain period of time and should be used until it expires. Once the token expires, a new X-NEXT-GEN-CSO token is returned in the head of the response. A new authentication token can also be obtained by using the authentication service.

#### <span id="page-8-1"></span>Immediate Searches

Immediate searches return the first page of results in the initial response. If there is more than one page of results, use the URL parameter (see the [Pagination](#page-58-3) section) to retrieve one page at a time.

#### <span id="page-8-2"></span>Case Search – JSON

Search for a specific case by case number.

**POST:** https://{pclapiurl}/pcl-public-api/rest/cases/find

#### Request header:

```
Content-type: application/json
Accept: application/json
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

#### Request body:

```
{ 
 "caseNumberFull": "1:2002bk20340" 
}
```

```
{
 "receipt": {
 "transactionDate": "2020-12-18T11:01:48.267-0600",
 "billablePages": 1,
 "loginId": "yourpacerusername",
 "clientCode": "",
 "firmId": "",
 "search": "All Courts; Name Henderson, Nicholas; Page: 1",
 "description": "All Court Types Party Search",
 "csoId": 3655344,
 "reportId": "e9c66eab-80b0-48fe-bcbe-62eec7bf59b8",
 "searchFee": ".10"
 },
 "pageInfo": {
 "number": 0,
 "size": 54,
 "totalPages": 1,
 "totalElements": 2,
 "numberOfElements": 2,
 "first": true,
 "last": true
 },
 "content": [
 {
 "courtId": "ilndc",
 "caseId": 306781,
 "caseYear": 2015,
 "caseNumber": 1445,
 "lastName": "Henderson",
 "firstName": "Nicholas",
 "middleName": " ",
 "generation": " ",
 "partyType": "pty",
 "partyRole": "dft",
 "jurisdictionType": "Civil",
 "courtCase": {
 "courtId": "ilndc",
 "caseId": 306781,
 "caseYear": 2015,
 "caseNumber": 1445,
 "caseOffice": "1",
 "caseType": "cv",
 "caseTitle": "Lytx, Inc. v. Sanderson",
 "dateFiled": "2015-02-17",
 "effectiveDateClosed": "2015-03-12",
 "natureOfSuit": "890",
 "jurisdictionType": "Civil",
 "caseLink": "https://ecf.ilnd.uscourts.gov/cgi-
bin/iqquerymenu.pl?306781",
 "caseNumberFull": "1:2015cv01445"
 },
 "dateFiled": "2015-02-17",
 "effectiveDateClosed": "2015-03-12",
 "natureOfSuit": "890",
 "caseOffice": "1",
 "caseType": "cv",
 "caseTitle": "Lytx, Inc. v. Sanderson",
 "caseNumberFull": "1:2015cv01445"
 },
```

#### <span id="page-10-0"></span>Case Search – XML

Search for a specific case by case number.

**POST:** https://{pclapiurl}/pcl-public-api/rest/cases/find

#### Request header:

```
Content-type: application/xml
Accept: application/xml
X-NEXT-GEN-
CSO:your128characterauthenticationtokentobeuseduntilexpirationyour128characte
rauthenticationtokentobeuseduntilexpirationyour128chara
```

#### Request body:

```
<caseSearch xmlns="https://pacer.uscourts.gov">
 <caseNumberFull>2000-90150</caseNumberFull>
</caseSearch>
```

```
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
 <caseList xmlns="https://pacer.uscourts.gov">
 <receipt>
 <transactionDate>2020-12-18T12:34:15.501-06:00</transactionDate>
 <billablePages>1</billablePages>
 <loginId>yourpacerusername</loginId>
 <clientCode></clientCode>
 <firmId></firmId>
 <search>All Courts; Case Number 90150; Case Year 2000; Case Number 2000-
90150; Page: 1</search>
 <description>All Court Types Case Search</description>
 <csoId>3655344</csoId>
 <reportId>6c08ede4-ee24-4350-b607-a4ebd8d694ac</reportId>
 <searchFee>.10</searchFee>
 </receipt>
 <pageInfo>
 <number>0</number>
 <size>54</size>
 <totalPages>1</totalPages>
 <totalElements>6</totalElements>
 <numberOfElements>6</numberOfElements>
 <first>true</first>
 <last>true</last>
 </pageInfo>
 <content>
 <case>
 <courtId>ilsbk</courtId>
 <caseId>998881</caseId>
 <caseYear>2000</caseYear>
 <caseNumber>90150</caseNumber>
 <caseOffice>1</caseOffice>
 <caseType>ap</caseType>
 <caseTitle>Bayne and Internal Revenue Service</caseTitle>
 <dateFiled>2000-11-23</dateFiled>
 <effectiveDateClosed>2001-02-28</effectiveDateClosed>
 <jurisdictionType>Bankruptcy</jurisdictionType>
 <caseNumberFull>1:2000ap90150</caseNumberFull>
 </case>
…… continued ……
```

#### <span id="page-12-0"></span>Party Search - JSON

**EXAMPLE 1:** Search for a party name with first and last name. **POST:** https://{pclapiurl}/pcl-public-api/rest/parties/find

#### Request header:

```
Content-type: application/json
Accept: application/json
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

#### Request body:

```
{ 
 "lastName": "Henderson", 
 "firstName":"Nicholas"
}
```

```
{
 "receipt": {
 "transactionDate": "2020-12-18T11:01:48.267-0600",
 "billablePages": 1,
 "loginId": "yourpacerusername",
 "search": "All Courts; Name Henderson, Nicholas; Page: 1",
 "description": "All Court Types Party Search",
 "csoId": 9655344,
 "reportId": "e9c66eab-80b0-48fe-bcbe-62eec7bf59b8",
 "searchFee": ".10"
 },
 "pageInfo": {
 "number": 0,
 "size": 54,
 "totalPages": 1,
 "totalElements": 2,
 "numberOfElements": 2,
 "first": true,
 "last": true
 },
 "content": [
 {
 "courtId": "ilndc",
 "caseId": 306781,
 "caseYear": 2015,
 "caseNumber": 1445,
 "lastName": "Henderson",
 "firstName": "Nicholas",
 "partyType": "pty",
 "partyRole": "dft",
 "jurisdictionType": "Civil",
 "courtCase": {
 "courtId": "ilsdc",
 "caseId": 306781,
 "caseYear": 2010,
 "caseNumber": 91445,
 "caseOffice": "1",
 "caseType": "cv",
 "caseTitle": "Wingz, Inc. v. Henderson",
 "dateFiled": "2010-02-17",
 "effectiveDateClosed": "2010-03-12",
 "natureOfSuit": "890",
 "jurisdictionType": "Civil",
 "caseLink": "https://ecf.ilnd.uscourts.gov/cgi-bin/iqquerymenu.pl?9306781",
 "caseNumberFull": "1:2010cv91445"
 },
 "dateFiled": "2010-02-17",
 "effectiveDateClosed": "2010-03-12",
 "natureOfSuit": "890",
 "caseOffice": "1",
 "caseType": "cv",
 "caseTitle": "Wingz, Inc. v. Henderson",
 "caseNumberFull": "1:2010cv91445"
 },
…… continued ……
```

**EXAMPLE 2:** Search for a party by SSN and last name.

**POST:** https://{pclapiurl}/pcl-public-api/rest/parties/find

#### Request header:

```
Content-type: application/json
Accept: application/json
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

#### Request body:

```
{
       "lastName": "smith",
       "ssn": "123456789"
}
```

```
{
 "receipt": {
 "transactionDate": "2024-11-20T13:01:54.190-0600",
 "billablePages": 1,
 "loginId": "yourpacerusername",
 "clientCode": "",
 "firmId": "",
 "search": "All Courts; Name smith; SSN 123456789; Page: 1",
 "description": "All Court Types Party Search",
 "csoId": 9655344,
 "reportId": "9a834569-cc5b-41c4-9a70-71bfb5bdd236",
 "searchFee": ".10"
 },
 "pageInfo": {
 "number": 0,
 "size": 54,
 "totalPages": 1,
 "totalElements": 9,
 "numberOfElements": 9,
 "first": true,
 "last": true
 },
 "content": [
 {
 "courtId": "laebk",
 "caseId": 144631,
 "caseYear": 2006,
 "caseNumber": 10011,
 "lastName": "Smith",
 "firstName": "Matt",
 "middleName": " ",
 "generation": " ",
 "partyType": "pty",
 "partyRole": "db",
 "jurisdictionType": "Bankruptcy",
 "courtCase": {
 "courtId": "laebk",
 "caseId": 144631,
 "caseYear": 2006,
 "caseNumber": 10011,
 "caseOffice": "2",
 "caseType": "bk",
 "caseTitle": "Sample Client",
 "dateFiled": "2006-01-06",
 "dateTermed": "2006-02-03",
 "dateDismissed": "2006-01-20",
 "bankruptcyChapter": "7",
 "dispositionMethod": "Dismissed for Other Reason",
 "jointBankruptcyFlag": "n",
 "jurisdictionType": "Bankruptcy",
 "effectiveDateClosed": "2006-02-03",
 "caseLink": "https://ecf.laeb.uscourts.gov/cgi-bin/iqquerymenu.pl?144631",
 "caseNumberFull": "2:2006bk10011"
 },
 "bankruptcyChapter": "7",
 "dateFiled": "2006-01-06",
 "dateDismissed": "2006-01-20",
 "dateTermed": "2006-02-03",
 "caseNumberFull": "2:2006bk10011",
 "caseOffice": "2",
 "caseType": "bk",
 "caseTitle": "Sample Client",
 "disposition": "Dismissed for Other Reason"
 }
 ],
 "masterCase": null
}
```

#### <span id="page-16-0"></span>Party Search - XML

**EXAMPLE 1:** Search for a party name with first and last name. **POST:** https://{pclapiurl}/pcl-public-api/rest/parties/find

#### Request header:

```
Content-type: application/xml
Accept: application/xml
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

#### Request body:

```
<partySearch xmlns="https://pacer.uscourts.gov">
 <lastName>Henderson</lastName> 
 <firstName>Nicholas</firstName>
</partySearch>
```

```
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<partyList xmlns="https://pacer.uscourts.gov">
 <receipt>
 <transactionDate>2020-12-18T13:40:17.384-06:00</transactionDate>
 <billablePages>1</billablePages>
 <loginId>yourpaceruser</loginId>
 <clientCode></clientCode>
 <firmId></firmId>
 <search>All Courts; Name Henderson, Nicholas; Page: 1</search>
 <description>All Court Types Party Search</description>
 <csoId>3655344</csoId>
 <reportId>17fd1ae3-398d-4915-99c2-289618cd4404</reportId>
 <searchFee>.10</searchFee>
 </receipt>
 <pageInfo>
 <number>0</number>
 <size>54</size>
 <totalPages>1</totalPages>
 <totalElements>2</totalElements>
 <numberOfElements>2</numberOfElements>
 <first>true</first>
 <last>true</last>
 </pageInfo>
 <content>
 <party>
 <courtId>ilndc</courtId>
 <caseId>306781</caseId>
 <caseYear>2010</caseYear>
 <caseNumber>91445</caseNumber>
 <lastName>Henderson</lastName>
 <firstName>Nicholas</firstName>
 <middleName> </middleName>
 <generation> </generation>
 <partyType>pty</partyType>
 <partyRole>dft</partyRole>
 <jurisdictionType>Civil</jurisdictionType>
 <courtCase>
 <courtId>ilndc</courtId>
 <caseId>306781</caseId>
 <caseYear>2015</caseYear>
 <caseNumber>1445</caseNumber>
 <caseOffice>1</caseOffice>
 <caseType>cv</caseType>
 <caseTitle>Wingz, Inc. v. Henderson</caseTitle>
 <dateFiled>2010-02-17</dateFiled>
 <effectiveDateClosed>2010-03-12</effectiveDateClosed>
 <natureOfSuit>890</natureOfSuit>
 <jurisdictionType>Civil</jurisdictionType>
 <caseLink>https://ecf.ilnd.uscourts.gov/cgi-
bin/iqquerymenu.pl?9306781</caseLink>
 <caseNumberFull>1:2010cv91445</caseNumberFull>
 </courtCase>
 <caseNumberFull>1:2010cv01445</caseNumberFull>
 <caseOffice>1</caseOffice>
 <caseTitle>Wingz, Inc. v. Henderson</caseTitle>
 <caseType>cv</caseType>
 <dateFiled>2010-02-17</dateFiled>
 <effectiveDateClosed>2010-03-12</effectiveDateClosed>
 <natureOfSuit>890</natureOfSuit>
 </party>
…… continued ……
```

**EXAMPLE 2:** Search for a party by SSN and last name. **POST:** https://{pclapiurl}/pcl-public-api/rest/parties/find

#### Request header:

```
Content-type: application/xml
Accept: application/xml
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

#### Request body:

```
<partySearch xmlns="https://pacer.uscourts.gov">
      <lastName>smith</lastName>
      <ssn>999999999</ssn>
</partySearch>
```

```
<?xml version="1.0" encoding="UTF-8"?><partyList xmlns="https://pacer.uscourts.gov">
 <receipt>
 <transactionDate>2024-11-20T12:43:31.449-06:00</transactionDate>
 <billablePages>1</billablePages>
 <loginId>yourpacerusername</loginId>
 <clientCode/>
 <firmId/>
 <search>All Courts; Name smith; SSN 123456789; Page: 1</search>
 <description>All Court Types Party Search</description>
 <csoId>9655344</csoId>
 <reportId>461220a6-5eaa-4239-b56d-6d52a444c075</reportId>
 <searchFee>.10</searchFee>
 </receipt>
 <pageInfo>
 <number>0</number>
 <size>54</size>
 <totalPages>1</totalPages>
 <totalElements>9</totalElements>
 <numberOfElements>9</numberOfElements>
 <first>true</first>
 <last>true</last>
 </pageInfo>
 <content>
 <party>
 <courtId>laebk</courtId>
 <caseId>144631</caseId>
 <caseYear>2006</caseYear>
 <caseNumber>10011</caseNumber>
 <lastName>Smith</lastName>
 <firstName>Matt</firstName>
 <middleName> </middleName>
 <generation> </generation>
 <partyType>pty</partyType>
 <partyRole>db</partyRole>
 <jurisdictionType>Bankruptcy</jurisdictionType>
 <courtCase>
 <courtId>laebk</courtId>
 <caseId>144631</caseId>
 <caseYear>2006</caseYear>
 <caseNumber>10011</caseNumber>
 <caseOffice>2</caseOffice>
 <caseType>bk</caseType>
 <caseTitle>Sample Client</caseTitle>
 <dateFiled>2006-01-06</dateFiled>
 <dateTermed>2006-02-03</dateTermed>
 <dateDismissed>2006-01-20</dateDismissed>
 <bankruptcyChapter>7</bankruptcyChapter>
 <dispositionMethod>Dismissed for Other Reason</dispositionMethod>
 <jointBankruptcyFlag>n</jointBankruptcyFlag>
 <jurisdictionType>Bankruptcy</jurisdictionType>
 <effectiveDateClosed>2006-02-03</effectiveDateClosed>
 <caseLink>https://ecf.laeb.uscourts.gov/cgi-bin/iqquerymenu.pl?144631</caseLink>
 <caseNumberFull>2:2006bk10011</caseNumberFull>
 </courtCase>
 <bankruptcyChapter>7</bankruptcyChapter>
 <caseNumberFull>2:2006bk10011</caseNumberFull>
 <caseOffice>2</caseOffice>
 <caseTitle>Sample Client</caseTitle>
 <caseType>bk</caseType>
 <dateDismissed>2006-01-20</dateDismissed>
 <dateFiled>2006-01-06</dateFiled>
 <dateTermed>2006-02-03</dateTermed>
 <disposition>Dismissed for Other Reason</disposition>
 </party>
 </content>
</partyList>
```

```
Advanced Searches
```

```
Example: Cases closed from 01/01/2016 to 02/01/2016
   Endpoint: https://{pclapiurl}/pcl-public-api/rest/cases/find
   JSON:
   { 
 "effectiveDateClosedFrom": "2016-01-01", 
 "effectiveDateClosedTo":"2016-02-01"
   }
   XML:
   <caseSearch xmlns="https://pacer.uscourts.gov"> 
 <effectiveDateClosedFrom>2016-01-01</effectiveDateClosedFrom> 
 <effectiveDateClosedTo>2016-02-01</effectiveDateClosedTo>
   </caseSearch>
   Example: Parties in cases with cases closed 01/01/2016 to 02/01/2016
   Endpoint: https://{pclapiurl}/pcl-public-api/rest/parties/find
   JSON:
   { 
 "courtCase": {
 "effectiveDateClosedFrom": "2015-02-02", 
 "effectiveDateClosedTo":"2015-02-02"
 }
      }
 XML:
 <partySearch xmlns="https://pacer.uscourts.gov"> 
 <courtCase>
 <effectiveDateClosedFrom>2016-01-01</effectiveDateClosedFrom> 
 <effectiveDateClosedTo>2016-02-01</effectiveDateClosedTo>
 </courtCase>
   </partySearch>
   Example: Search for all chapter 13 bankruptcy cases with a party last name "Smith" filed in a 
   specific month
   Endpoint: https://{pclapiurl}/pcl-public-api/rest/cases/find
   JSON:
   { 
    "party": {
    "lastName": "Smith"
    },
    "federalBankruptcyChapter" : [ 13 ],
    "dateFiledFrom": "2016-01-01", 
    "dateFiledTo":"2016-01-31" 
   }
   XML:
   <caseSearch xmlns="https://pacer.uscourts.gov">
    <federalBankruptcyChapter>13</federalBankruptcyChapter>
```

<dateFiledFrom>2016-01-01</dateFiledFrom>

```
 <dateFiledTo>2016-01-31</dateFiledTo>
 <party>
 <role>db</role>
 </party>
</caseSearch>
Example: Search for all chapter 13 bankruptcy debtors filed in a specific month
Endpoint: https://{pclapiurl}/pcl-public-api/rest/parties/find
JSON:
{ 
 "courtCase": {
 "federalBankruptcyChapter" : [ 13 ],
 "dateFiledFrom": "2016-01-01", 
 "dateFiledTo":"2016-01-31" 
 },
 "role" : [ "db" ]
 }
XML:
<partySearch xmlns="https://pacer.uscourts.gov"> 
 <courtCase>
 <federalBankruptcyChapter>13</federalBankruptcyChapter>
 <dateFiledFrom>2016-01-01</dateFiledFrom>
 <dateFiledTo>2016-01-31</dateFiledTo>
   </courtCase>
 <role>db</role>
</partySearch>
Example: Cases that have parties with a name like Robbins, B Filed in Illinois; Chapter 7, 13
Endpoint: https://{pclapiurl}/pcl-public-api/rest/cases/find
JSON:
{ 
 "party": {
 "lastName": "Robbins",
 "firstName": "B" 
 },
 "dateFiledFrom": "2014-01-01", 
 "dateFiledTo":"2015-01-01",
 "federalBankruptcyChapter": [ 7, 13 ],
 "courtId": [ "il" ]
}
XML:
<caseSearch xmlns="https://pacer.uscourts.gov">
 <party>
 <lastName>Robbins</lastName>
 <firstName>C</firstName>
 </party>
```

 <dateFiledFrom>2014-01-01</dateFiledFrom> <dateFiledTo>2015-01-01</dateFiledTo>

<federalBankruptcyChapter>7</federalBankruptcyChapter>

```
 <courtId>IL</courtId>
</caseSearch>
Example: Parties with a name like Robbins, B in Court ID ILC, ILN, ILS; Chapter 7, 13
Endpoint: https://{pclapiurl}/pcl-public-api/rest/parties/find
JSON:
{ 
 "lastName": "Robbins",
 "firstName": "C",
 "courtCase": {
 "dateFiledFrom": "2014-01-01", 
 "dateFiledTo":"2015-01-01",
 "federalBankruptcyChapter": [ 7, 13 ],
 "courtId": [ "il" ]
 }
}
XML:
<partySearch xmlns="https://pacer.uscourts.gov">
 <lastName>Robbins</lastName>
 <firstName>C</firstName>
 <courtCase>
 <dateFiledFrom>2014-01-01</dateFiledFrom>
 <dateFiledTo>2015-01-01</dateFiledTo>
 <federalBankruptcyChapter>7</federalBankruptcyChapter>
 <federalBankruptcyChapter>13</federalBankruptcyChapter>
 <courtId>IL</courtId>
 </courtCase>
</partySearch>
Example: Cases with a party Name Ca Nature of Suit 830
Endpoint: https://{pclapiurl}/pcl-public-api/rest/cases/find
JSON:
{ 
 "party": {
 "lastName": "Ca"
 },
 "dateFiledFrom": "2015-01-01",
 "dateFiledTo": "2015-04-01",
 "natureOfSuit": ["830"]
}
XML:
<caseSearch xmlns="https://pacer.uscourts.gov">
 <party>
 <lastName>Ca</lastName>
 </party>
 <dateFiledFrom>2014-01-01</dateFiledFrom>
```

 <dateFiledTo>2015-01-01</dateFiledTo> <natureOfSuit>830</natureOfSuit>

<federalBankruptcyChapter>13</federalBankruptcyChapter>

```
Example: Parties filed by Name like Ca Nature of Suit 830
Endpoint: https://{pclapiurl}/pcl-public-api/rest/parties/find
JSON:
{ 
 "lastName": "Ca",
 "courtCase": {
 "dateFiledFrom": "2015-01-01",
 "dateFiledTo": "2015-04-01",
 "natureOfSuit": ["830"]
 }
}
XML:
<partySearch xmlns="https://pacer.uscourts.gov">
 <lastName>Ca</lastName>
 <courtCase>>
 <dateFiledFrom>2014-01-01</dateFiledFrom>
 <dateFiledTo>2015-01-01</dateFiledTo>
 <natureOfSuit>830</natureOfSuit>
 </courtCase>
</partySearch>
```

Example: Exact Match on name fields. Search all parties with party last name Smith and first name John with no middle initial.

```
Endpoint: https://{pclapiurl}/pcl-public-api/rest/parties/find
JSON:
{
   "lastName": "Smith",
   "firstName": "John",
   "middleName": "",
   "exactNameMatch": true
}
XML:
<partySearch xmlns="https://pacer.uscourts.gov">
 <firstName>John</firstName>
   <lastName>Smith</lastName>
   <middleName></middleName>
   <exactNameMatch>true</exactNameMatch>
</partySearch>
```

```
Example: Cases filed at various courts with multiple date ranges.
Endpoint: https://{pclapiurl}/pcl-public-api/rest/cases/find
JSON:
{
 "jurisdictionType": "bk",
```

```
 "caseType": [
 "cv", "ncrim", "misc"
 ],
 "courtId": [
 "IA", "IAN", "IAS", "NV"
 ],
 "dateFiledFrom": "2000-01-01",
 "dateFiledTo": "2020-01-01",
 "effectiveDateClosedFrom": "2000-01-01",
 "effectiveDateClosedTo": "2020-01-01",
 "dateDismissedFrom": "2000-01-01",
 "dateDismissedTo": "2020-01-01",
 "dateDischargedFrom": "2000-01-01",
 "dateDischargedTo": "2020-01-01",
 "federalBankruptcyChapter": [
 "7", "15"
 ],
 "natureOfSuit": [
 "140", "151"
 ]
}
XML:
<caseSearch xmlns="https://pacer.uscourts.gov">
 <jurisdictionType>bk</jurisdictionType> 
 <caseType>
 <element>cv</element>
 <element>ncrim</element>
 <element>misc</element>
 </caseType>
 <courtId>
 <element>IA</element>
 <element>IAN</element>
 <element>IAS</element>
 <element>NV</element>
 </courtId>
 <dateFiledFrom>2000-01-01</dateFiledFrom>
 <dateFiledTo>2020-01-01</dateFiledTo>
 <effectiveDateClosedFrom>2000-01-01</effectiveDateClosedFrom>
 <effectiveDateClosedTo>2020-01-01</effectiveDateClosedTo> 
 <dateDismissedFrom>2000-01-01</dateDismissedFrom>
 <dateDismissedTo>2020-01-01</dateDismissedTo> 
 <dateDischargedFrom>2000-01-01</dateDischargedFrom>
 <dateDischargedTo>2020-01-01</dateDischargedTo>
 <federalBankruptcyChapter>
 <element>7</element>
 <element>15</element>
 </federalBankruptcyChapter>
 <natureOfSuit>
 <element>140</element>
 <element>151</element>
 </natureOfSuit>
</caseSearch>
```

```
Example: Parties with specific name and various case parameters
Endpoint: https://{pclapiurl}/pcl-public-api/rest/parties/find
JSON:
{
 "lastName": "Henderson",
 "firstName": "Nicholas",
 "exactNameMatch": false,
 "courtCase": {
 "jurisdictionType": "bk",
 "caseType": [
 "cv", "ncrim", "misc"
 ],
 "courtId": [
 "ilcbk", "ilcdc"
 ],
 "dateFiledFrom": "2000-01-01",
 "dateFiledTo": "2020-01-01",
 "effectiveDateClosedFrom": "2000-01-01",
 "effectiveDateClosedTo": "2020-01-01",
 "dateDismissedFrom": "2000-01-01",
 "dateDismissedTo": "2020-01-01",
 "dateDischargedFrom": "2000-01-01",
 "dateDischargedTo": "2020-01-01",
 "federalBankruptcyChapter": [
 "7", "15"
 ],
 "natureOfSuit": [
 "140", "151"
 ]
 },
 "searchName": "Henderson",
 "searchType": "PARTY"
}
XML:
<partySearch xmlns="https://pacer.uscourts.gov">
 <courtCase>
 <caseId />
 <caseNumber />
 <caseNumberFull />
 <caseOffice />
 <caseTitle />
 <caseType>
 <element>cv</element>
 <element>ncrim</element>
 <element>misc</element>
 </caseType>
 <caseYear />
 <courtId>
 <element>ilcbk</element>
 <element>ilcdc</element>
 </courtId>
 <dateDischargedFrom>2000-01-01</dateDischargedFrom>
 <dateDischargedTo>2020-01-01</dateDischargedTo>
 <dateDismissedFrom>2000-01-01</dateDismissedFrom>
```

```
 <dateDismissedTo>2020-01-01</dateDismissedTo>
   <dateFiledFrom>2000-01-01</dateFiledFrom>
   <dateFiledTo>2020-01-01</dateFiledTo>
   <effectiveDateClosedFrom>2000-01-01</effectiveDateClosedFrom>
   <effectiveDateClosedTo>2020-01-01</effectiveDateClosedTo>
   <federalBankruptcyChapter>
   <element>7</element>
   <element>15</element>
   </federalBankruptcyChapter>
   <jurisdictionType>bk</jurisdictionType>
   <nos>
   <element>140</element>
   <element>151</element>
   </nos>
   </courtCase>
   <exactNameMatch>false</exactNameMatch>
   <firstName>Nicholas</firstName>
   <generation />
   <lastName>Henderson</lastName>
   <middleName />
   <partyRole />
   <partyType />
   <searchName>Henderson</searchName>
   <searchType>PARTY</searchType>
</partySearch>
```

#### <span id="page-27-0"></span>Batch Searches

Batch searches function similarly to immediate searches except that the results of batch searches are queued for later download. The benefit of batch searches is that they allow for a much larger set of search results. In addition, immediate searches require multiple requests to page through results, while batch searches return all rows in a single request. The maximum number of batch search results is 108,000.

#### Batch Search

Except for the target URL, invoking a batch search (case or party) is exactly the same as invoking an immediate search. However, the object returned is different, as it provides the status of the batch job, its unique identifier, and the criteria provided.

The number of batch jobs that can run at the same time is limited. Depending on the search criteria, a batch job can take several minutes to complete. The batch status API service call can track the status of each job from WAITING to RUNNING to COMPLETE. The limits on running and stored batch jobs are subject to change and can be increased or decreased depending on system resource availability.

The number of batch jobs that are stored is also limited. The batch job delete API service call is available to remove completed batch jobs. Users must clean batch jobs as they are collected or no longer needed. The limits on running and stored batch jobs are subject to change and can be increased or decreased depending on system resource availability.

```
HttpURLConnection conn = null;
try {
 // this URL is for batch case searches. Note that to perform batch party
 // searches, replace 'cases' with 'parties'
 URL url = new URL("https://qa-pcl.uscourts.gov/pcl-public-api/rest" + 
 "/cases/download");
 conn = (HttpURLConnection) url.openConnection();
 conn.setDoOutput(true);
 conn.setRequestMethod("POST");
 conn.setRequestProperty("Content-Type", "application/json");
 conn.setRequestProperty("Accept", "application/xml");
 conn.setRequestProperty("X-NEXT-GEN-CSO", nextGenCsoKey);
 // search for all parties with last names starting with 'Smith' in cases filed
 // on or after January 1, 2010.
 String searchBody = "{ \"caseTitle\": \"Smith\" }";
 OutputStream os = conn.getOutputStream();
 os.write(searchBody.getBytes());
 os.flush();
 InputStreamReader isr = new InputStreamReader((conn.getInputStream()));
 // stream batch job start results into a BufferedReader
 BufferedReader br = new BufferedReader(isr);
 // Process results similarly to Case Search, including checking for new key
}
catch (IOException e) {
 // NOTE that an IOException with HTTP response code 401 means that an invalid
 // or expired NextGenCSO key was provided and 406 means that an invalid
 // search parameter was provided.
 e.printStackTrace();
 System.exit(-1);
}
finally {
 if (conn != null) {
 conn.disconnect();
 }
}
```

Example: Batch case search

#### Batch Job Statuses

When a batch job is started, only its initial status is returned. Therefore, you should check the status of a batch search before attempting to download the results.

The PCL API allows you to query the status of a single batch search or of all currently running and completed batch searches of a certain type (i.e., case or party).

This example shows the retrieval of the status of all batch case searches.

```
HttpURLConnection conn = null;
try {
 // this URL is for batch case search statuses. Note that to request batch party
 // search statuses, replace 'cases' with 'parties'
 URL url = new URL("https://qa-pcl.uscourts.gov/pcl-public-api/rest" + 
 "/cases/reports");
 conn = (HttpURLConnection) url.openConnection();
 conn.setDoOutput(true);
 conn.setRequestMethod("GET");
 conn.setRequestProperty("Content-Type", "application/json");
 conn.setRequestProperty("Accept", "application/xml");
 conn.setRequestProperty("X-NEXT-GEN-CSO", nextGenCsoKey);
 int responseCode = conn.getResponseCode();
 if (responseCode == HttpURLConnection.HTTP_OK) {
 InputStreamReader isr = new InputStreamReader((conn.getInputStream()));
 BufferedReader br = new BufferedReader(isr);
 String responseLine;
 StringBuilder requestResponse = new StringBuilder();
 while ((responseLine = br.readLine()) != null) {
 requestResponse.append(responseLine);
 }
 System.out.println(requestResponse.toString());
 isr.close();
 } else {
 return;
 }
}
catch (IOException e) {
 // NOTE that an IOException with HTTP response code 401 means that an invalid
 // or expired NextGenCSO key was provided 
 e.printStackTrace();
 System.exit(-1);
}
finally {
 if (conn != null) {
 conn.disconnect();
 }
}
```

Example: Requesting the status of all batch case searches

#### Download Batch Search Results: POST vs. GET

When a batch search is complete, the results can be downloaded. The returned search results are in the same format as those returned by the immediate case and party searches.

```
HttpURLConnection conn = null;
Integer reportId = 401; // the ID for the report to download
try {
 // this URL is for batch case search statuses. Note that to request batch party
 // search statuses, replace 'cases' with 'parties'
 URL url = new URL("https://qa-pcl.uscourts.gov/pcl-public-api/rest" + 
 "/cases/download/" + reportId);
 conn = (HttpURLConnection) url.openConnection();
 conn.setDoOutput(true);
 conn.setRequestMethod("GET");
 conn.setRequestProperty("Content-Type", "application/json");
 conn.setRequestProperty("Accept", "application/xml");
 conn.setRequestProperty("X-NEXT-GEN-CSO", nextGenCsoKey);
 int responseCode = conn.getResponseCode();
 if (responseCode == HttpURLConnection.HTTP_OK) {
 isr = new InputStreamReader((conn.getInputStream()));
 BufferedReader br = new BufferedReader(isr);
 String responseLine;
 StringBuilder requestResponse = new StringBuilder();
 while ((responseLine = br.readLine()) != null) {
 requestResponse.append(responseLine);
 }
 System.out.println(requestResponse.toString());
 isr.close();
 } else {
 return;
 }
}
catch (IOException e) {
 // NOTE that an IOException with HTTP response code 401 means that an invalid
 // or expired NextGenCSO key was provided 
 e.printStackTrace();
 System.exit(-1);
}
finally {
 if (conn != null) {
 conn.disconnect();
 }
}
```

Example: Downloading the results of a batch case search with a report ID of 401

#### Delete Batch Search Results

The PCL API limits the number of batch searches that may run concurrently and the number of completed batch searches a user may retain to 10. **NOTE:** This number is subject to change.

Therefore, once the results of a batch search have been downloaded, you should delete the results of the search from the PCL system.

```
HttpURLConnection conn = null;
Integer reportId = 401; // the ID for the report to download
try {
 // this URL is for deleting batch case search results and batch party search 
 //results. 
 URL url = new URL("https://qa-pcl.uscourts.gov/pcl-public-api/rest" + 
 "/cases/reports/" + reportId);
 conn = (HttpURLConnection) url.openConnection();
 conn.setDoOutput(true);
 conn.setRequestMethod("DELETE");
 conn.setRequestProperty("Content-Type", "application/json");
 conn.setRequestProperty("Accept", "application/xml");
 conn.setRequestProperty("X-NEXT-GEN-CSO", nextGenCsoKey);
 int responseCode = conn.getResponseCode();
 if (responseCode == HttpURLConnection.HTTP_NO_CONTENT) {
 System.out.println("The specified batch job was deleted.\n");
 } else {
 System.out.println("No results returned. HTTP Response Code: [" +
 responseCode + "].\n");
 }
}
catch (IOException e) {
 // NOTE that an IOException with HTTP response code 401 means that an invalid
 // or expired NextGenCSO key was provided 
 e.printStackTrace();
 System.exit(-1);
}
finally {
 if (conn != null) {
 conn.disconnect();
 }
}
```

Example: Deleting the results of a batch case search with a report ID of 401

#### <span id="page-32-0"></span>**Batch Search Examples**

Batch search requests require the same request headers and are in the same JSON or XML format as immediate search requests. The batch search is different in that it does not return results one page at a time. The search is initiated with one service call, and results are retrieved with another service call. More services are available to view the status of a batch jobs, list batch jobs, and delete batch search results.

#### <span id="page-32-1"></span>Start a Batch Case Search - JSON

**POST:** https://{pclapiurl}/pcl-public-api/rest/cases/download

#### Request header:

```
Content-type: application/json
Accept: application/json
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

#### Request body:

```
{ 
 "caseNumberFull": "12-20340", 
 "courtId":[ "insbk" ] 
}
```

```
{
 "reportId": 1078,
 "status": "RUNNING",
 "startTime": null,
 "endTime": null,
 "recordCount": null,
 "unbilledPageCount": null,
 "downloadFee": null,
 "pages": null,
 "sort": {
 "orders": []
 },
 "searchType": "COURT_CASE",
 "criteria": {
 "searchType": "COURT_CASE",
 "courtId": [
 "insbk"
 ],
 "caseYear": 2012,
 "caseNumber": 20340,
 "requestType": "Batch",
 "requestSource": "Other",
 "caseNumberFull": "12-20340",
 "caseType": [],
 "federalBankruptcyChapter": [],
 "natureOfSuit": []
 }
}
```

#### <span id="page-33-0"></span>Start Batch Case Search - XML

**POST:** https://{pclapiurl}/pcl-public-api/rest/cases/dowload

#### Request header:

```
Content-type: application/xml
Accept: application/xml
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

#### Request body:

```
<caseSearch xmlns="https://pacer.uscourts.gov">
 <caseTitle>Falls</caseTitle>
</caseSearch>
```

#### Response body:

```
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<reportInfo xmlns="https://pacer.uscourts.gov">
 <reportId>1079</reportId>
 <status>RUNNING</status>
 <sort/>
 <caseCriteria>
 <requestType>Batch</requestType>
 <requestSource>Other</requestSource>
 <searchType>COURT_CASE</searchType>
 <caseTitle>Falls vs</caseTitle>
 </caseCriteria>
</reportInfo>
```

#### <span id="page-33-1"></span>Get Batch Job Status - JSON

**GET:** https://{pclapiurl}/pcl-public-api/rest/cases/download/status/{reportId}

#### Request header:

```
Accept: application/json
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

Response body:

```
{
 "reportId": 1080,
 "status": "COMPLETED",
 "startTime": "2020-12-18T14:46:44.000-0600",
 "endTime": "2020-12-18T14:46:44.000-0600",
 "recordCount": 42,
 "unbilledPageCount": 0,
 "downloadFee": 0.0,
 "pages": 1,
 "sort": {
 "orders": []
 },
 "searchType": "COURT_CASE",
 "criteria": {
 "searchType": "COURT_CASE",
 "courtId": [],
 "requestType": "Batch",
 "requestSource": "Other",
 "caseType": [],
 "caseTitle": "Falls",
 "federalBankruptcyChapter": [],
 "natureOfSuit": []
 }
}
```

#### <span id="page-34-0"></span>Get Batch Job Status - XML

**GET:** https://{pclapiurl}/pcl-public-api/rest/cases/download/status/{reportId}

#### Request header:

```
Accept: application/xml
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

```
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<reportInfo xmlns="https://pacer.uscourts.gov">
 <reportId>1080</reportId>
 <status>COMPLETED</status>
 <startTime>2020-12-18T15:19:14.000-0600</startTime>
 <endTime>2020-12-18T15:19:14.000-0600</endTime>
 <recordCount>42</recordCount>
 <unbilledPageCount>0</unbilledPageCount>
 <downloadFee>0.0</downloadFee>
 <pages>1</pages>
 <sort/>
 <caseCriteria>
 <requestType>Batch</requestType>
 <requestSource>Other</requestSource>
 <searchType>COURT_CASE</searchType>
 <caseTitle>Falls</caseTitle>
 </caseCriteria>
</reportInfo>
```

#### <span id="page-35-0"></span>Get List of Batch Jobs – JSON

**GET:** https://{pclapiurl}/pcl-public-api/rest/cases/reports

#### Request header:

```
Accept: application/json
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

```
{
 "receipt": null,
 "pageInfo": {
 "number": 0,
 "size": 54,
 "totalPages": 1,
 "totalElements": 5,
 "numberOfElements": 5,
 "first": true,
 "last": true
 },
 "content": [
 {
 "reportId": 1077,
 "status": "COMPLETED",
 "startTime": "2020-12-18T14:35:29.000-0600",
 "endTime": "2020-12-18T14:35:29.000-0600",
 "recordCount": 9,
 "unbilledPageCount": 0,
 "downloadFee": 0.0,
 "pages": 1,
 "criteria": {
 "searchType": "PARTY",
 "courtId": [],
 "requestType": "Batch",
 "requestSource": "Other",
 "role": [],
 "exactNameMatch": false,
 "ssn": "111111111"
 },
 "sort": {
 "orders": []
 }
 },
…… continued ……
```

#### <span id="page-36-0"></span>Get List of Batch Jobs – XML

**GET:** https://{pclapiurl}/pcl-public-api/rest/cases/reports

#### Request header:

```
Accept: application/xml
X-NEXT-GEN-CSO:
your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic
ationtokentobeuseduntilexpirationyour128chara
```

```
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<reportList xmlns="https://pacer.uscourts.gov">
 <pageInfo>
 <number>0</number>
 <size>54</size>
 <totalPages>1</totalPages>
 <totalElements>5</totalElements>
 <numberOfElements>5</numberOfElements>
 <first>true</first>
 <last>true</last>
 </pageInfo>
 <content>
 <report>
 <reportId>1077</reportId>
 <status>COMPLETED</status>
 <startTime>2020-12-18T14:35:29.000-0600</startTime>
 <endTime>2020-12-18T14:35:29.000-0600</endTime>
 <recordCount>9</recordCount>
 <unbilledPageCount>0</unbilledPageCount>
 <downloadFee>0.0</downloadFee>
 <pages>1</pages>
 <partyCriteria>
 <requestType>Batch</requestType>
 <requestSource>Other</requestSource>
 <searchType>PARTY</searchType>
 <exactNameMatch>false</exactNameMatch>
 <ssn>111111111</ssn>
 </partyCriteria>
 <sort/>
 </report>
…… continued ……
```

#### <span id="page-37-0"></span>Get Batch Job Results - JSON

**GET:** https://{pclapiurl}/pcl-public-api/rest/cases/download/{reportId}

#### Request header:

```
Accepts: application/json
X-NEXT-GEN-
CSO:your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthe
nticationtokentobeuseduntilexpirationyour128chara
```

#### Response body:

```
{
 "content": [
 {
 "courtId": "02lca",
 "caseId": "20830",
 "caseYear": "2001",
 "caseNumber": "100",
 "caseOffice": "0",
 "caseType": "ap",
 "caseTitle": "Griffin v Coombe",
 "dateFiled": "2001-05-01",
 "natureOfSuit": "3550",
 "caseNumberFull": "0:2001ap00100"
 },
…… continued ……
```

#### <span id="page-37-1"></span>Get Batch Job Results - XML

**GET:** https://{pclapiurl}/pcl-public-api/rest/cases/download/{reportId}

#### Request header:

```
Accept: application/xml
X-NEXT-GEN-
CSO:your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthe
nticationtokentobeuseduntilexpirationyour128chara
```

```
<?xml version="1.0" encoding="UTF-8"?>
<download xmlns="https://pacer.uscourts.gov">
 <content>
 <courtCase>
 <courtId>02lca</courtId>
 <caseId>20830</caseId>
 <caseYear>2001</caseYear>
 <caseNumber>100</caseNumber>
 <caseOffice>0</caseOffice>
 <caseType>ap</caseType>
 <caseTitle>Griffin v Coombe</caseTitle>
 <dateFiled>2001-05-01</dateFiled>
 <natureOfSuit>3550</natureOfSuit>
 <caseNumberFull>0:2001ap00100</caseNumberFull>
 </courtCase>
…… continued ……
```

#### Delete a Batch Job - JSON

**DELETE:** https://{pclapiurl}/pcl-public-api/rest/cases/reports/{reportId}

#### Request header:

Accept: application/json X-NEXT-GEN-CSO:

your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic ationtokentobeuseduntilexpirationyour128chara

#### Response:

HTTP 204

#### Delete a Batch Job - XML

**DELETE:** https://{pclapiurl}/pcl-public-api/rest/cases/reports/{reportId}

#### Request header:

Accept: application/xml

X-NEXT-GEN-CSO:

your128characterauthenticationtokentobeuseduntilexpirationyour128characterauthentic ationtokentobeuseduntilexpirationyour128chara

#### Response:

HTTP 204

## <span id="page-39-0"></span>PCL Search API

The PCL Search API can be used to search for federal court cases or for parties associated with federal cases. Each service accepts the PCL search criteria in either XML or JSON formats. Successful service responses will return an HTTP 200 response code. Services predicated with the "/cases" path will return a list of court cases. Services with the "/parties" path will return a list of parties.

#### <span id="page-39-1"></span>**Setting the Headers**

All PCL API search requests require the same request headers, including the token returned from the authentication service call (nextGenCSO). This token should be included in the X-NEXT-GEN-CSO request header of each request.

The following headers are required for all PCL search API requests:

- **Content-type:** This header indicates the content of the request body. Valid values are "application/xml" for XML requests and "application/json" for JSON requests.
- **X-NEXT-GEN-CSO:** This header should contain the authentication token from the PACER authentication service. Failure to set this header will result in a 401 (user is unauthorized) error.

The following headers are optional:

- **Accept:** This header determines the type of response returned by the server. The application currently supports a response of "application/json" and "application/xml." If the Accept header is not set, then the default response is "application/json."
- **X-CLIENT-CODE:** This allows the user to tag billing transactions to a specific client.

## <span id="page-40-0"></span>API Endpoints

#### <span id="page-40-1"></span>**Basic Searches**

#### **Searching for Cases**

PCL API searches can either return one page of data at a time or an entire result set, depending on the API endpoint. The /find endpoint returns search results on a page-by-page basis and allows for pagination through the search results.

Description: Search for cases that match search criteria. The first page of results (up to 54

matches) is returned immediately. Other pages of the results can be accessed page by page using URL parameters (page=#). Pages are billed as they are

retrieved.

Service: /cases/find Method: POST

URL Sorting and pagination options (see the [Sorting](#page-58-0) and [Pagination](#page-58-3) sections

parameter: below for examples) Request body: CourtCaseSearchDto

Search criteria in XML and JSON format

Response ReportListType

body:

#### **Searching for Parties**

As with case searches, the party searches can either return one page of data at a time or an entire result set, depending on the API endpoint. The /find endpoint returns search results on a pageby-page basis and allows for pagination through the search results.

Description: Search for matching cases with party data. The first page of results (up to

54 matches) are returned immediately. Other pages of the results can be accessed page by page using URL parameters (page=#). Pages are billed as

they are retrieved.

Service: /parties/find

Method: POST

URL Sorting and pagination options (see the [Sorting](#page-58-0) and [Pagination](#page-58-3) sections

parameter: below for examples) Request body: PartySearchDto Response body: ReportListType

#### <span id="page-40-2"></span>**Batch Jobs**

#### **Starting Report Jobs**

The /download endpoint will return a report ID that can be used to later retrieve the entire result set. This means you must make one service call to start the search and another to retrieve the results. Once the results are retrieved, the user is billed for the total number of pages in the search results. A maximum of 108,000 results (2,000 pages) can be retrieved using this service.

Description: Start a case search batch job.

Service: /cases/download

Method: POST

Request body: CourtCaseSearchDto Response ReportInfoType

body: The report ID used to retrieve search results is included in the response.

#### **Retrieving Report Jobs**

Once a report job has completed, the results can be retrieved using this service.

Description: Retrieve full results from the case search batch job.

Service: /cases/download/{reportId}

Method: GET

URL parameter: reportId is the ID of the report from the ReportInfoType returned when the

job started.

Response body: ReportListType

Included in this response are the downloadable number of pages, along with billing information. The user is charged once to download any given report

job.

#### **Case Report Job Maintenance**

These services maintain PCL API search jobs. Report jobs that are started using the /download service may need to be removed. Use the following services to view the status of current report jobs and remove old reports.

Description: Retrieve the status of a batch search job. Service: /cases/download/status/{reportId}

Method: GET

URL parameter: reportId is the ID of the report.

Response body: ReportListType

Included in the response are number of pages along with the original search criteria. If the report does not exist, then the user will receive a response saying the report is not found. There is no charge for checking on the status

of a report.

Description: List all current batch jobs.

Service: /cases/reports

Method: GET

Response body: ReportListType

A list of all report jobs currently on the PCL system is included in the

response.

Description: Remove an existing batch job. The user can only host a limited number of

report jobs on the server. Once the limit is reached, the user **must** delete

existing reports to run new ones.

Service: /cases/reports/{reportId}

Method: DELETE

Response body:

#### **Starting Party Report Jobs**

The /download endpoint will return a report ID that can be used to later retrieve the entire result set. This means you must make one service call to start the search and another to retrieve the results. Once the results are retrieved, the user is billed for the total number of pages in the search results. A maximum of 100,000 results can be retrieved using this service.

Description: Start a party search batch job.

Service: /parties/download

Method: POST

Request body: PartySearchDto Response body: ReportInfoType

Included in the response is a report ID used to retrieve the search results.

#### **Retrieving Report Jobs**

Once a report job has completed, the results can be retrieved using this service.

Description: Retrieve full results from the case search batch job.

Service: /parties/download/{reportId}

Method: GET

URL parameter: reportId is the ID of the report.

Response body: ReportListType

#### **Party Report Job Maintenance**

These services are used to maintain PCL API search jobs. Report jobs that are started using the /download service may need to be removed. Use the following services to view the status of current report jobs and remove old reports.

Description: Retrieve the status of the batch search job. Service: /parties/download/status/{reportId}

Method: GET

URL parameter: reportId is the ID of the report.

Response body: ReportListType

Description: List all batch jobs. Service: /parties/reports

Method: GET

Response body: ReportListType

Description: Remove an existing batch job. Service: /parties/reports/{reportId}

Method: DELETE

## Search Criteria—Data Definitions

The current search criteria are based on the existing PCL application. The backend API validates the search criteria before submitting the request to the database.

#### Case Searches – Searchable Fields

<span id="page-43-1"></span><span id="page-43-0"></span>

|                  | ALL COURT TYPES |                                                           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |  |
|------------------|-----------------|-----------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--|
| API Field(s)     | Type            | Description                                               | Format                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |  |
| jurisdictionType | String          | Jurisdiction type of the case                             | •<br>ap for appellate cases<br>•<br>bk for bankruptcy cases<br>•<br>cr for criminal cases<br>•<br>cv for civil cases<br>•<br>mdl for Judicial Panel Multidistrict Litigation (JPML)<br>cases                                                                                                                                                                                                                                                                                                        |  |
| caseId           | Integer         | Sequentially generated number that<br>identifies the case | Integer maximum: 2,147,483,647                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |  |
| caseNumberFull   | String          | Case number                                               | When all elements are present in the case number, the<br>most common format is<br>o:yy-tp-nnnnn, where "o" is a<br>single-digit integer that specifies the office and "tp" is<br>the two-character case type.<br>Users may or may not have all of the elements of the<br>case number, so the following formats should be<br>accepted:<br>•<br>yy-nnnnn<br>•<br>yy-tp-nnnnn<br>•<br>yy tp nnnnn<br>•<br>yytpnnnnn<br>•<br>o:yy-nnnnn<br>•<br>o:yy-tp-nnnnn<br>•<br>o:yy tp nnnnn<br>•<br>o:yytpnnnnn |  |

| caseTitle                                               | String       | The title by which the case is commonly<br>known                                                                                                                           | Text field that is not case-sensitive and accepts<br>alphanumeric and special characters.<br>Maximum length: 254                                                                                                                                                                                                                                                                  |
|---------------------------------------------------------|--------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| caseOffice                                              | String       | The divisional office in which the case<br>was filed                                                                                                                       | One alphanumeric character                                                                                                                                                                                                                                                                                                                                                        |
| caseNumber                                              | String       | The sequence number of the case                                                                                                                                            | Five-digit number                                                                                                                                                                                                                                                                                                                                                                 |
| caseType                                                | List[String] | Code that identifies the type of case                                                                                                                                      | Text field that accepts letters, numbers, and special<br>characters.<br>Maximum length: 6                                                                                                                                                                                                                                                                                         |
| caseYear                                                | String       | The last two digits of the year in which<br>the case was filed                                                                                                             | Two-digit or four-digit year                                                                                                                                                                                                                                                                                                                                                      |
| courtId                                                 | List[String] | The general geographical region or<br>specific court district                                                                                                              | The court ID is the abbreviation of the court location<br>combined with the court type (dc or bk).<br>Maximum length: 6 characters<br>For a complete list of valid court IDs and regions, see<br>Appendix A. More information about the role and<br>structure of the U.S. courts can be found here:<br>https://www.uscourts.gov/about-federal-courts/court<br>role-and-structure. |
| dateFiledFrom and<br>dateFiledTo                        | Date         | Filing date of the case, generated during<br>case opening                                                                                                                  | Date in the format yyyy-MM-dd                                                                                                                                                                                                                                                                                                                                                     |
| effectiveDateClosedFrom<br>and<br>effectiveDateClosedTo | Date         | Filing date of the most recent docket<br>entry that terminated (closed) the case<br>(if a case was closed and reopened,<br>there could have been multiple<br>terminations) | Date in the format yyyy-MM-dd                                                                                                                                                                                                                                                                                                                                                     |
|                                                         |              | BANKRUPTCY CASES ONLY                                                                                                                                                      |                                                                                                                                                                                                                                                                                                                                                                                   |
| API Field(s)                                            | Type         | Description                                                                                                                                                                | Format                                                                                                                                                                                                                                                                                                                                                                            |
| federalBankruptcyChapter                                | List[String] | Federal bankruptcy chapter under<br>which the case is filed                                                                                                                | •<br>7: Chapter 7<br>•<br>9: Chapter 9<br>•<br>11: Chapter 11<br>•<br>13: Chapter 13<br>•<br>15: Chapter 15                                                                                                                                                                                                                                                                       |

|                        |              |                                         | •<br>304: Chapter 304                                   |
|------------------------|--------------|-----------------------------------------|---------------------------------------------------------|
|                        |              |                                         | For more on bankruptcy chapters, see Appendix B.        |
| dateDismissedFrom and  | Date         | Date range of bankruptcy case dismissal | Date in the format yyyy-MM-dd                           |
| dateDismissedTo        |              |                                         |                                                         |
| dateDischargedFrom and | Date         | Date range of bankruptcy case           | Date in the format yyyy-MM-dd                           |
| dateDischargedTo       |              | discharge                               |                                                         |
|                        |              | CIVIL AND APPELLATE CASES ONLY          |                                                         |
| API Field(s)           | Type         | Description                             | Format                                                  |
| natureOfSuit           | List[String] | Nature of suit for the case             | Three or four digits                                    |
|                        |              |                                         | See valid values for civil nature of suit in Appendix C |
|                        |              |                                         | and appellate nature of suit in Appendix D.             |
|                        |              | JPML CASES ONLY                         |                                                         |
| API Field(s)           | Type         | Description                             | Format                                                  |
| jpmlNumber             | Integer      | Master JPML case number                 | Integer representing the JPML master case number        |
|                        |              |                                         | Maximum: 6 digits                                       |

```
{ 
 "jurisdictionType": "",
 "caseId" :"",
 "caseNumberFull": "",
 "caseTitle": "",
 "caseOffice": "",
 "caseNumber": "",
 "caseType": [
 ""
 ],
 "caseYear": "",
 "courtId": [
 ""
 ],
 "dateFiledFrom": "",
 "dateFiledTo": "",
 "effectiveDateClosedFrom": "",
 "effectiveDateClosedTo":"",
 "federalBankruptcyChapter": [
 ""
 ],
 "dateDismissedFrom": "",
 "dateDismissedTo": "",
 "dateDischargedFrom": "",
 "dateDischargedTo": "",
 "natureOfSuit": [
 ""
 ],
 "jpmlNumber" : 
}
```

#### Case Search – JSON Representation Case Search – XML Representation

```
<caseSearch xmlns="https://pacer.uscourts.gov">
 <jurisdictionType></jurisdictionType>
 <caseId></caseId>
 <caseNumberFull></caseNumberFull>
 <caseTitle></caseTitle>
 <caseOffice></caseOffice>
 <caseNumber></caseNumber>
 <caseType>
 <element></element>
 </caseType>
 <caseYear></caseYear>
 <courtId>
 <element </element>
 </courtId>
 <dateFiledFrom></dateFiledFrom>
 <dateFiledTo></dateFiledTo>
 <effectiveDateClosedFrom></effectiveDateClosedFrom>
 <effectiveDateClosedTo></effectiveDateClosedTo>
 <federalBankruptcyChapter>
 <element></element>
 </federalBankruptcyChapter>
 <dateDismissedFrom></dateDismissedFrom>
 <dateDismissedTo></dateDismissedTo>
 <dateDischargedFrom></dateDischargedFrom>
 <dateDischargedTo></dateDischargedTo>
 <natureOfSuit>
 <element></element>
 </natureOfSuit>
 <jpmlNumber></jpmlNumber>
</caseSearch>
```

#### Party Searches – Searchable Fields

This section includes any of the following fields optionally combined with Case Searches – Searchable Fields. A minimally valid search will include at least one of the following:

- Last name (also used to search for a non-person entity)
- Social Security number (SSN), only for bankruptcy debtors
- Date filed (from or to)
- Date closed (from or to)
- Date dismissed (from or to)
- Date discharged (from or to)

Party searches may also include elements of court case searches to refine the results. Case elements of a party search are provided via an included **courtCase** nested object. See the Court Case – Searchable Fields section of this manual for the search field available.

<span id="page-47-0"></span>For example, to limit a party search for parties with the last name "Smith" to only cases filed on or after January 1, 2010, provide the following JSON object:

```
{
 "lastName": "Smith",
 "courtCase": {
 "dateFiledFrom": "2010-01-01"
 }
}
```

**NOTE:** Search field names are case sensitive, but search values are not.

| PARTY SEARCH INPUT OPTIONS |              |                                                                                                                                                                                                                                                                                                    |                                                                                                                                                                                                                                                                                               |  |
|----------------------------|--------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--|
| API Field(s)               | Type         | Description                                                                                                                                                                                                                                                                                        | Format                                                                                                                                                                                                                                                                                        |  |
| reportId                   | String       | User-supplied identifier that is returned with<br>search results                                                                                                                                                                                                                                   | This field has no effect on the search or the results of<br>the search but is useful for identifying a search.                                                                                                                                                                                |  |
| courtId                    | List[String] | The geographical region or specific court<br>district                                                                                                                                                                                                                                              | See Appendix E<br>for a list of valid regions for each<br>environment.                                                                                                                                                                                                                        |  |
| caseId                     | Integer      | A unique identifier for each case                                                                                                                                                                                                                                                                  |                                                                                                                                                                                                                                                                                               |  |
| caseNumberFull             | String       | A formatted case number                                                                                                                                                                                                                                                                            | Case numbers may be entered in each of the<br>following formats:<br>•<br>yy-nnnnn<br>•<br>yy-tp-nnnnn                                                                                                                                                                                         |  |
|                            |              |                                                                                                                                                                                                                                                                                                    | •<br>yy tp nnnnn                                                                                                                                                                                                                                                                              |  |
|                            |              |                                                                                                                                                                                                                                                                                                    | •<br>yytpnnnnn                                                                                                                                                                                                                                                                                |  |
|                            |              |                                                                                                                                                                                                                                                                                                    | •<br>o:yy-nnnnn                                                                                                                                                                                                                                                                               |  |
|                            |              |                                                                                                                                                                                                                                                                                                    | •<br>o:yy-tp-nnnnn                                                                                                                                                                                                                                                                            |  |
|                            |              |                                                                                                                                                                                                                                                                                                    | •<br>o:yy tp nnnnn                                                                                                                                                                                                                                                                            |  |
|                            |              |                                                                                                                                                                                                                                                                                                    | •<br>o:yytpnnnnn                                                                                                                                                                                                                                                                              |  |
|                            |              |                                                                                                                                                                                                                                                                                                    | where:<br>"yy"<br>is case year (may be 2 or 4 digits)<br>"nnnn"<br>is case number (up to 5 digits)<br>"tp"<br>is case type (up to 2 characters)<br>"o"<br>is the office where the case was filed (1 digit)<br>NOTE:<br>Case type and office values are ignored for<br>appellate case numbers. |  |
| lastName                   | String       | The last name of a party to search. This field<br>is also used to search for a non-person entity.<br>If the exactMatches<br>flag is not set to "true,"<br>the lastName parameter is a "starts with"<br>search parameter that will match any last<br>name that starts with the included characters. | Alphanumeric value of last name                                                                                                                                                                                                                                                               |  |
| firstName                  | String       | The first name of a party to search.                                                                                                                                                                                                                                                               | Alphanumeric value of first name                                                                                                                                                                                                                                                              |  |

|                |              | If the exactMatches<br>flag is not set, the<br>lastName parameter is a "starts with"<br>search<br>parameter that will match any last name that<br>starts with the included characters. |                                                                                                                                                                                                                                                        |
|----------------|--------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| middleName     | String       | The middle name of a party to search.                                                                                                                                                  | Alphanumeric value of middle name                                                                                                                                                                                                                      |
|                |              | If the exactMatches<br>flag is not set, the<br>lastName parameter is a "starts with"<br>search<br>parameter that will match any last name that<br>starts with the included characters. |                                                                                                                                                                                                                                                        |
| generation     | String       | The name suffix (e.g., III, MD)                                                                                                                                                        | String length maximum: 5                                                                                                                                                                                                                               |
|                |              | This is an exact match field for length and<br>capitalization.                                                                                                                         |                                                                                                                                                                                                                                                        |
| partyType      | String       | The court-assigned party type for a party<br>involved in a case                                                                                                                        | Party type codes are created and assigned by<br>individual courts, and as such, their meanings can vary<br>from court to court.                                                                                                                        |
| role           | List[String] | The court-assigned role for a party to a case                                                                                                                                          | Party role codes are created and assigned by individual<br>courts, and as such, their meanings can vary from<br>court to court.                                                                                                                        |
|                |              |                                                                                                                                                                                        | NOTE:<br>Because the PCL does not receive party role<br>information for appellate cases, a search including<br>party roles will not return appellate cases, even if the<br>search would have returned appellate cases if the role<br>had been omitted. |
| exactNameMatch | Boolean      | By default, any party name value provided<br>will return any party whose name starts with<br>that value.                                                                               | {<br>"lastName": "Smith",<br>"exactNameMatch": true<br>}                                                                                                                                                                                               |
|                |              | Set exactNameMatch<br>to "true" to override<br>that behavior and return only names that<br>exactly match what is entered.                                                              |                                                                                                                                                                                                                                                        |

| caseYearFrom     | Integer | Limit results to those of cases from the year<br>specified and later   | 4-digit integer value maximum                                                                                                                                                                                                                          |
|------------------|---------|------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| caseYearTo       | Integer | Limit results to those of cases from the year<br>specified and earlier | 4-digit integer value maximum                                                                                                                                                                                                                          |
| jurisdictionType | String  |                                                                        | The most common jurisdiction types are:<br>•<br>ap<br>for appellate cases<br>•<br>bk<br>for bankruptcy cases<br>•<br>cr<br>for criminal cases<br>•<br>cv<br>for civil cases<br>•<br>mdl<br>for Judicial Panel Multidistrict Litigation<br>(JPML) cases |
| ssn              | String  | Search for parties with a particular SSN.                              | See Appendix F<br>for a complete list of known valid<br>case types for each environment.<br>Must be all-numeric values; may include dashes but                                                                                                         |
|                  |         |                                                                        | not required.<br>When specified, a last name/entity name must also be<br>specified.                                                                                                                                                                    |
| ssn4             | String  | Search for parties whose SSN ends with a<br>specified four digits.     | When specified, a last name/entity name must also be<br>specified.                                                                                                                                                                                     |

```
{ 
 "reportId": "",
 "courtId": [
 ""
 ],
 "caseId" :"",
 "caseNumberFull": "",
 "lastName": "",
 "firstName": "",
 "middleName": "",
 "generation": "",
 "partyType": "",
 "partyRole": "",
 "exactNameMatch": ,
 "caseYearFrom": "",
 "caseYearTo": "",
 "jurisdictionType": "",
 "ssn": "",
 "ssn4": ""
}
```

#### Party Search – JSON Representation Party Search – XML Representation

```
<partySearch xmlns="https://pacer.uscourts.gov">
 <reportId></reportId>
 <courtId>
 <element />
 </courtId>
 <caseId></caseId>
 <caseNumberFull></caseNumberFull>
 <lastName></lastName>
 <firstName></firstName>
 <middleName></middleName>
 <generation></generation>
 <partyRole></partyRole>
 <partyType></partyType>
 <exactNameMatch></exactNameMatch>
 <caseYearFrom></caseYearFrom>
 <caseYearTo></caseYearTo>
 <jurisdictionType></jurisdictionType>
 <ssn></ssn>
 <ssn4></ssn4>
</partySearch>
```

## Search Results—Data Definitions

### Case Search Results

<span id="page-52-1"></span><span id="page-52-0"></span>

|                  | ALL COURT TYPES |                                                                                              |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |  |
|------------------|-----------------|----------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--|
| API Field(s)     | Type            | Description                                                                                  | Format                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |  |
| caseLink         | String          | Link to case in the case<br>management/electronic case files<br>(CM/ECF) system at the court | URL of the case in CM/ECF                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |  |
| jurisdictionType | String          | Jurisdiction type of the case                                                                | •<br>ap for appellate cases<br>•<br>bk for bankruptcy cases<br>•<br>cr for criminal cases<br>•<br>cv for civil cases<br>•<br>mdl for Judicial Panel Multidistrict Litigation<br>(JPML) cases                                                                                                                                                                                                                                                                                                         |  |
| caseId           | Integer         | Sequentially generated number that<br>identifies the case                                    | Integer maximum: 2,147,483,647                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |  |
| caseNumberFull   | String          | Case number                                                                                  | When all elements are present in the case number, the<br>most common format is<br>o:yy-tp-nnnnn, where "o" is a<br>single-digit integer that specifies the office, and "tp" is<br>the two-character case type.<br>Users may or may not have all of the elements of the<br>case number, so the following formats should be<br>accepted:<br>•<br>yy-nnnnn<br>•<br>yy-tp-nnnnn<br>•<br>yy tp nnnnn<br>•<br>yytpnnnnn<br>•<br>o:yy-nnnnn<br>•<br>o:yy-tp-nnnnn<br>•<br>o:yy tp nnnnn<br>•<br>o:yytpnnnnn |  |

| caseTitle                                                    | String       | The title by which the case is commonly<br>known                                                                                                                        | Text field that is not case-sensitive and accepts<br>alphanumeric and special characters<br>Maximum length: 254                                                                                                                                                                                                                                                                    |
|--------------------------------------------------------------|--------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| caseOffice                                                   | String       | The divisional office in which the case was<br>filed                                                                                                                    | One alphanumeric character                                                                                                                                                                                                                                                                                                                                                         |
| caseNumber                                                   | String       | The sequence number of the case                                                                                                                                         | Five-digit number                                                                                                                                                                                                                                                                                                                                                                  |
| caseType                                                     | String       | Code that identifies the type of case                                                                                                                                   | Text field that accepts letters, numbers, and special<br>characters<br>Maximum length: 6                                                                                                                                                                                                                                                                                           |
| caseYear                                                     | Short        | The last two digits of the year in which the<br>case was filed                                                                                                          | Two-<br>or four-digit year                                                                                                                                                                                                                                                                                                                                                         |
| courtId                                                      | List[String] | The general geographical region or specific<br>court district                                                                                                           | The court ID is the abbreviation of the court location<br>combined with the court type (dc or bk).<br>Maximum length: 6 characters.<br>For a complete list of valid court IDs and regions, see<br>Appendix A. More information about the role and<br>structure of the U.S. courts can be found here:<br>https://www.uscourts.gov/about-federal<br>courts/court-role-and-structure. |
| dateFiledFrom and<br>dateFiledTo                             | Date         | Filing date of the case, generated during<br>case opening                                                                                                               | Date in the format yyyy-mm-dd                                                                                                                                                                                                                                                                                                                                                      |
| effectiveDateClose<br>dFrom and<br>effectiveDateClose<br>dTo | Date         | Filing date of the most recent docket entry<br>that terminated (closed) the case (if a case<br>was closed and reopened, there could have<br>been multiple terminations) | Date in the format yyyy-mm-dd                                                                                                                                                                                                                                                                                                                                                      |
|                                                              |              | BANKRUPTCY CASES ONLY                                                                                                                                                   |                                                                                                                                                                                                                                                                                                                                                                                    |
| API Field(s)                                                 | Type         | Description                                                                                                                                                             | Format                                                                                                                                                                                                                                                                                                                                                                             |
| federalBankruptcy<br>Chapter                                 | List[String] | Federal bankruptcy chapter under which<br>the case is filed                                                                                                             | •<br>7: Chapter 7<br>•<br>9: Chapter 9<br>•<br>11: Chapter 11<br>•<br>13: Chapter 13<br>•<br>15: Chapter 15<br>304: Chapter 304<br>•                                                                                                                                                                                                                                               |

|                                               |              |                                                                                                           | For more information on bankruptcy chapters, see                                                                                   |
|-----------------------------------------------|--------------|-----------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
|                                               |              |                                                                                                           | Appendix B.                                                                                                                        |
| dateDismissedFrom<br>and<br>dateDismissedTo   | Date         | Date range of bankruptcy case dismissal                                                                   | Date in the format yyyy-MM-dd                                                                                                      |
| dateDischargedFrom<br>and<br>dateDischargedTo | Date         | Date range of bankruptcy case discharge                                                                   | Date in the format yyyy-MM-dd                                                                                                      |
|                                               |              | CIVIL AND APPELLATE CASES ONLY                                                                            |                                                                                                                                    |
| API Field(s)                                  | Type         | Description                                                                                               | Format                                                                                                                             |
| natureOfSuit                                  | List[String] | Nature of suit for the case                                                                               | Three or four digits.<br>See valid values for civil nature of<br>suit in Appendix C and appellate nature of suit in<br>Appendix D. |
|                                               |              | JPML CASES ONLY                                                                                           |                                                                                                                                    |
| API Field(s)                                  | Type         | Description                                                                                               | Format                                                                                                                             |
| jpmlNumber                                    | Integer      | Master JPML case number                                                                                   | Integer representing the JPML master case number<br>Maximum: 6 digits                                                              |
|                                               |              | JPML MASTER CASES ONLY                                                                                    |                                                                                                                                    |
| API Field(s)                                  | Type         | Description                                                                                               | Format                                                                                                                             |
| jpmlNumber                                    | Integer      |                                                                                                           |                                                                                                                                    |
|                                               |              | PAGE INFO                                                                                                 |                                                                                                                                    |
| API Field(s)                                  | Type         | Description                                                                                               | Format                                                                                                                             |
| number                                        | Integer      | Page number returned                                                                                      | Integer maximum: 2,147,483,647                                                                                                     |
| size                                          | Integer      | Page size (54)                                                                                            | Maximum page size 54                                                                                                               |
| totalPages                                    | Integer      | Total pages of data available                                                                             | Integer maximum: 2,147,483,647                                                                                                     |
| totalElements                                 | Long         | Total number of records available                                                                         |                                                                                                                                    |
| numberOfElements                              | Integer      | Number of records returned (NOTE:<br>Not<br>applicable for batch report requests)                         | Maximum long value:<br>9,223,372,036,854,775,807                                                                                   |
| first                                         | Boolean      | Indicates if the current page is the first page<br>(NOTE:<br>Not applicable for batch report<br>requests) | True or false                                                                                                                      |

| last | Boolean | Indicates if the current page is the last page | True or false |
|------|---------|------------------------------------------------|---------------|
|      |         | (NOTE:<br>Not applicable for batch report      |               |
|      |         | requests)                                      |               |

#### Party Search Results

This section includes all Case search results.

<span id="page-55-0"></span>

|              |        | ALL COURT TYPES                            |                           |
|--------------|--------|--------------------------------------------|---------------------------|
| API Field(s) | Type   | Description                                | Format                    |
| lastName     | String | Last name of the party                     | Alphanumeric text field   |
|              |        |                                            | Maximum: 200 characters   |
| firstName    | String | First name of the party                    | Alphanumeric text field   |
|              |        |                                            | Maximum: 50 characters    |
| middleName   | String | Middle name of the party                   | Alphanumeric text field   |
|              |        |                                            | Maximum: 10 characters    |
| generation   | String | Generation of the party, e.g., "jr", "III" | Alphanumeric text field   |
|              |        |                                            | Maximum: 5 characters     |
| partyType    | String | Code used to broadly classify the type of  | Alphanumeric text field   |
|              |        | person, e.g., "pty"                        | Maximum: 3 characters     |
| partyRole    | String | Used to record the role of the party in    | Alphanumeric text field   |
|              |        | the case, e.g., "dft," "pla," etc.         | Maximum: 10 characters    |
|              |        | REPORT INFO                                |                           |
| API Field(s) | Type   | Description                                | Format                    |
| reportId     | Long   | Unique ID for report                       | Maximum long value:       |
|              |        |                                            | 9,223,372,036,854,775,807 |
| status       | String | Status of the report                       | Enumeration values        |
|              |        |                                            |                           |
|              |        | Possible values:                           |                           |
|              |        | •<br>COMPLETED                             |                           |
|              |        | •<br>RUNNING                               |                           |
|              |        | •<br>WAITING                               |                           |
|              |        | •<br>FAILED                                |                           |

| startTime<br>Date |         |                                              | Time when the report generation       | yyyy-MM-dd'T'HH:mm:ss.SSSZ                            |  |                            |
|-------------------|---------|----------------------------------------------|---------------------------------------|-------------------------------------------------------|--|----------------------------|
|                   |         |                                              | started                               | (timezone="US/Central")                               |  |                            |
| endTime<br>Date   |         |                                              | Time when the report generation ended | yyyy-MM-dd'T'HH:mm:ss.SSSZ                            |  |                            |
|                   |         |                                              |                                       | (timezone="US/Central")                               |  |                            |
| recordCount       | Long    |                                              | Number of records in the report       | Maximum Long value:                                   |  |                            |
|                   |         |                                              |                                       | 9,223,372,036,854,775,807                             |  |                            |
| unbilledPageCount | Long    |                                              | Number of pages in report that have   | Maximum Long value:                                   |  |                            |
|                   |         |                                              | not been billed                       | 9,223,372,036,854,775,807                             |  |                            |
| downloadFee       | Double  |                                              | Cost to download the report           | Floating point number converted to dollar value       |  |                            |
| pages             | Long    |                                              | Number of pages in the report         | Maximum Long value:                                   |  |                            |
|                   |         |                                              |                                       | 9,223,372,036,854,775,807                             |  |                            |
|                   |         |                                              | RECEIPT                               |                                                       |  |                            |
| API Field         |         | Type                                         | Description                           | Format                                                |  |                            |
| transactionDate   | Date    |                                              | Timestamp of search transaction       | YYYY-MM-DDTHH:MM:SS.MS-TZ                             |  |                            |
| billablePages     | Integer |                                              | Number of billable pages              | Maximum: 2,147,483,647                                |  |                            |
| loginId           | String  |                                              | User login ID                         | Maximum length: 40                                    |  |                            |
| search            | String  |                                              | Search criteria                       | Maximum length: 255                                   |  |                            |
| description       | String  |                                              | Search description                    | Maximum length: 100                                   |  |                            |
| csoId             | Integer |                                              | PACER account ID                      | Integer maximum: 2,147,483,647                        |  |                            |
| reportId          | Long    |                                              | Report ID                             | Maximum long value: 9,223,372,036,854,775,807         |  |                            |
| searchFee         | Double  |                                              | Fee for search                        | Floating point number converted to dollar value       |  |                            |
|                   |         |                                              | COURT CASE                            |                                                       |  |                            |
| API Field         |         | Type                                         | Description                           | Format                                                |  |                            |
| caseNumberFull    |         | String                                       | ID of the court. Case number can      | See Case Searches –<br>Searchable Fields table        |  |                            |
|                   |         |                                              | be used alone or with other search    |                                                       |  |                            |
|                   |         |                                              | criteria.                             |                                                       |  |                            |
| caseYearFrom      | Short   |                                              | Beginning case year for search        | Number between 0 and 2,100                            |  |                            |
| caseYearTo        | Short   |                                              | End case year for search              |                                                       |  | Number between 0 and 2,100 |
| jmplNumber        | Integer |                                              | JMPL number for search                | Integer                                               |  |                            |
| caseOffice        | String  |                                              | The case office                       | String max length: 2                                  |  |                            |
| caseType          |         | List[String]<br>Code identifies type of case |                                       | List of strings accepts letters, numbers, and special |  |                            |
|                   |         |                                              |                                       | characters. Maximum length: 6                         |  |                            |
| caseTitle         |         | String                                       | Title of the case                     | String of case title, accepts wildcards.              |  |                            |

| dateFiledFrom            | Date          | Search on the date filed start date            | yyyyy-mm-dd                                             |  |
|--------------------------|---------------|------------------------------------------------|---------------------------------------------------------|--|
| dateFiledTo              | Date          | Search on the date filed end date              | yyyyy-mm-dd                                             |  |
| effectiveDateClosedFrom  | Date          | Search on date close start date<br>yyyyy-mm-dd |                                                         |  |
| effectiveDateClosedTo    | Date          | Search on date closed end date                 | yyyyy-mm-dd                                             |  |
| dateReopenedFrom         | Date          | Date case was reopened start date              | yyyyy-mm-dd                                             |  |
| dateReopenedTo           | Date          | Date case was reopened end date                | yyyyy-mm-dd                                             |  |
| dateDismissedTo          | Date          | Date case dismissed start date                 | yyyyy-mm-dd                                             |  |
| dateDismissedFrom        | Date          | Date case dismissed end data                   | yyyyy-mm-dd                                             |  |
| dateDischargedTo         | Date          | Date case discharged start date                | yyyyy-mm-dd                                             |  |
| dateDischargedFrom       | Date          | Date case discharged end date                  | yyyyy-mm-dd                                             |  |
| federalBankruptcyChapter | List[String]  | List of valid bankruptcy chapters              | See Appendix B                                          |  |
| dispositionMethod        | String        | Disposition method of case                     | String with a maximum length of 100                     |  |
| dispoMethodJt            | String        | Joint disposition method of case               | String with a maximum length of 100                     |  |
| dateDismissedJtFrom      | Date          | Joint dismissed case start date                | yyyyy-mm-dd                                             |  |
| dateDismissedJtTo        | Date          | Joint dismissed case end date                  | yyyyy-mm-dd                                             |  |
| caseJoint                | Character     | Case joint                                     | Single character                                        |  |
| jurisdictionType         | String        | Court with jurisdiction                        | See Cases Searches –<br>Searchable Fields               |  |
| natureOfSuit             | List [String] | Nature of suit                                 | See Appendix C                                          |  |
| caseStatus               | Character     | Status of case                                 | Single character—valid status is "O" for open cases, or |  |
|                          |               |                                                | "C" for closed cases                                    |  |

## <span id="page-58-0"></span>Sorting

You may sort reports by specifying the sort fields using criteria parameters. You can sort on one or more fields in either descending (DESC) or ascending (ASC) order.

For example, to sort on case year descending and then within the year to sort on case type ascending, add the following parameters: **sort=caseYear,DESC&sort=caseType,ASC**,

**NOTE:** The order of the parameters is important, as case year is the primary sort field and case type is the secondary sort field.

#### <span id="page-58-1"></span>**Sortable Case Fields**

| courtId                                           | dateDismissed                                                                          | jpmlNumber                                                                             | mdlExtension                                                 |
|---------------------------------------------------|----------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|--------------------------------------------------------------|
| caseId                                            | dateDischarged                                                                         | mdlCourtId                                                                             | mdlTransfereeDistri<br>ct                                    |
| caseYear<br>caseNumber<br>caseOffice<br>caseType  | bankrupctyChapter<br>dispositionMethod<br>jointDispositionMethod<br>jointDismissedDate | civilDateInitiate<br>civilDateDisposition<br>civilDateTerminated<br>civilStatInitiated | mdlLittype<br>mdlStatus<br>mdlDateReceived<br>mdlDateOrdered |
| caseTitle<br>dateFiled<br>effectiveDateC<br>losed | jointDischargedDate<br>jointBankruptcyFlag<br>natureOfSuit                             | civilStatDisposition<br>civilStatTerminated<br>civilCtoNumber                          | mdlTransferee                                                |
| dateReopened                                      | jurisdictionType                                                                       | civilTransferee                                                                        |                                                              |

#### <span id="page-58-2"></span>**Sortable Party Fields**

| courtId    | partyType        |
|------------|------------------|
| caseId     | role             |
| caseYear   | jurisdictionType |
| caseNumber | seqNo            |
| lastName   | aliasEq          |
| firstName  | aliasType        |
| middleName | description      |
| generation |                  |

## <span id="page-58-3"></span>Pagination

Non-batch reports are returned in pages of 54 records each. The first page is page 0. If nothing is specified, then page 0 is returned. To return a specific page number, use the "page" parameter as indicated below.

For example, to request the third page, append **page=2** to your query URL.

## <span id="page-59-0"></span>Appendix A: Court IDs

| Court ID | Court Name                                 |
|----------|--------------------------------------------|
|          |                                            |
| 01bap    | U.S. Court of Appeals, First Circuit BAP   |
| 01ca     | U.S. Court of Appeals, First Circuit       |
| 02ca     | U.S. Court of Appeals, Second Circuit      |
| 03ca     | U.S. Court of Appeals, Third Circuit       |
| 04ca     | U.S. Court of Appeals, Fourth Circuit      |
| 05ca     | U.S. Court of Appeals, Fifth Circuit       |
| 06ca     | U.S. Court of Appeals, Sixth Circuit       |
| 07ca     | U.S. Court of Appeals, Seventh Circuit     |
| 08ca     | U.S. Court of Appeals, Eighth Circuit      |
| 09bap    | U.S. Court of Appeals, Ninth Circuit BAP   |
| 09ca     | U.S. Court of Appeals, Ninth Circuit       |
| 10ca     | U.S. Court of Appeals, Tenth Circuit       |
| 11ca     | U.S. Court of Appeals, Eleventh Circuit    |
| akbk     | Alaska Bankruptcy Court                    |
| akdc     | Alaska District Court                      |
| almbk    | Alabama Middle Bankruptcy Court            |
| almdc    | Alabama Middle District Court              |
| alnbk    | Alabama Northern Bankruptcy Court          |
| alndc    | Alabama Northern District Court            |
| alsbk    | Alabama Southern Bankruptcy Court          |
| alsdc    | Alabama Southern District Court            |
| arebk    | Arkansas Eastern Bankruptcy Court          |
| aredc    | Arkansas Eastern District Court            |
| arwbk    | Arkansas Western Bankruptcy Court          |
| arwdc    | Arkansas Western District Court            |
| azbk     | Arizona Bankruptcy Court                   |
| azdc     | Arizona District Court                     |
| cacbk    | California Central Bankruptcy Court        |
| cacdc    | California Central District Court          |
| caebk    | California Eastern Bankruptcy Court        |
| caedc    | California Eastern District Court          |
| cafc     | U.S. Court of Appeals, Federal Circuit     |
| canbk    | California Northern Bankruptcy Court       |
| candc    | California Northern District Court         |
| casbk    | California Southern Bankruptcy Court       |
| casdc    | California Southern District Court         |
| citdc    | United States Court of International Trade |
| cobk     | Colorado Bankruptcy Court                  |
| codc     | Colorado District Court                    |
| cofc     | United States Federal Claims Court         |
| ctbk     | Connecticut Bankruptcy Court               |
| ctdc     | Connecticut District Court                 |
| dcbk     | District Of Columbia Bankruptcy Court      |
| dcca     | U.S. Court of Appeals, D.C. Circuit        |
| dcdc     | District Of Columbia District Court        |
|          |                                            |

debk Delaware Bankruptcy Court dedc Delaware District Court

flmbk Florida Middle Bankruptcy Court flmdc Florida Middle District Court

flnbk Florida Northern Bankruptcy Court flndc Florida Northern District Court flsbk Florida Southern Bankruptcy Court flsdc Florida Southern District Court gambk Georgia Middle Bankruptcy Court gamdc Georgia Middle District Court ganbk Georgia Northern Bankruptcy Court gandc Georgia Northern District Court gasbk Georgia Southern Bankruptcy Court gasdc Georgia Southern District Court

gubk Guam Bankruptcy Court gudc Guam District Court hibk Hawaii Bankruptcy Court hidc Hawaii District Court

ianbk Iowa Northern Bankruptcy Court iandc Iowa Northern District Court iasbk Iowa Southern Bankruptcy Court iasdc Iowa Southern District Court idbk Idaho Bankruptcy Court iddc Idaho District Court

ilcbk Illinois Central Bankruptcy Court ilcdc Illinois Central District Court ilnbk Illinois Northern Bankruptcy Court ilndc Illinois Northern District Court ilsbk Illinois Southern Bankruptcy Court ilsdc Illinois Southern District Court innbk Indiana Northern Bankruptcy Court inndc Indiana Northern District Court insbk Indiana Southern Bankruptcy Court insdc Indiana Southern District Court

jpmldc Judicial Panel on Multidistrict Litigation

ksbk Kansas Bankruptcy Court ksdc Kansas District Court

kyebk Kentucky Eastern Bankruptcy Court kyedc Kentucky Eastern District Court kywbk Kentucky Western Bankruptcy Court kywdc Kentucky Western District Court laebk Louisiana Eastern Bankruptcy Court laedc Louisiana Eastern District Court lambk Louisiana Middle Bankruptcy Court lamdc Louisiana Middle District Court lawbk Louisiana Western Bankruptcy Court lawdc Louisiana Western District Court

mabk Massachusetts Bankruptcy Court madc Massachusetts District Court mdbk Maryland Bankruptcy Court mddc Maryland District Court mebk Maine Bankruptcy Court medc Maine District Court

miebk Michigan Eastern Bankruptcy Court miedc Michigan Eastern District Court miwbk Michigan Western Bankruptcy Court miwdc Michigan Western District Court mnbk Minnesota Bankruptcy Court mndc Minnesota District Court

moebk Missouri Eastern Bankruptcy Court moedc Missouri Eastern District Court mowbk Missouri Western Bankruptcy Court mowdc Missouri Western District Court

msnbk Mississippi Northern Bankruptcy Court msndc Mississippi Northern District Court mssbk Mississippi Southern Bankruptcy Court mssdc Mississippi Southern District Court

mtbk Montana Bankruptcy Court mtdc Montana District Court

ncebk North Carolina Eastern Bankruptcy Court ncedc North Carolina Eastern District Court ncmbk North Carolina Middle Bankruptcy Court ncmdc North Carolina Middle District Court ncwbk North Carolina Western Bankruptcy Court ncwdc North Carolina Western District Court

ndbk North Dakota Bankruptcy Court nddc North Dakota District Court nebk Nebraska Bankruptcy Court nedc Nebraska District Court

nhbk New Hampshire Bankruptcy Court nhdc New Hampshire District Court njbk New Jersey Bankruptcy Court njdc New Jersey District Court nmbk New Mexico Bankruptcy Court nmdc New Mexico District Court

nmidc Northern Mariana Islands District Court

nvbk Nevada Bankruptcy Court nvdc Nevada District Court

nyebk New York Eastern Bankruptcy Court nyedc New York Eastern District Court nynbk New York Northern Bankruptcy Court nyndc New York Northern District Court nysbk New York Southern Bankruptcy Court nysdc New York Southern District Court nywbk New York Western Bankruptcy Court

nywdc New York Western District Court ohnbk Ohio Northern Bankruptcy Court ohndc Ohio Northern District Court ohsbk Ohio Southern Bankruptcy Court ohsdc Ohio Southern District Court

okebk Oklahoma Eastern Bankruptcy Court okedc Oklahoma Eastern District Court oknbk Oklahoma Northern Bankruptcy Court okndc Oklahoma Northern District Court okwbk Oklahoma Western Bankruptcy Court okwdc Oklahoma Western District Court

orbk Oregon Bankruptcy Court ordc Oregon District Court

paebk Pennsylvania Eastern Bankruptcy Court paedc Pennsylvania Eastern District Court pambk Pennsylvania Middle Bankruptcy Court pamdc Pennsylvania Middle District Court pawbk Pennsylvania Western Bankruptcy Court pawdc Pennsylvania Western District Court

prbk Puerto Rico Bankruptcy Court prdc Puerto Rico District Court ribk Rhode Island Bankruptcy Court ridc Rhode Island District Court scbk South Carolina Bankruptcy Court scdc South Carolina District Court sdbk South Dakota Bankruptcy Court sddc South Dakota District Court

tnebk Tennessee Eastern Bankruptcy Court tnedc Tennessee Eastern District Court tnmbk Tennessee Middle Bankruptcy Court tnmdc Tennessee Middle District Court tnwbk Tennessee Western Bankruptcy Court tnwdc Tennessee Western District Court txebk Texas Eastern Bankruptcy Court txedc Texas Eastern District Court txnbk Texas Northern Bankruptcy Court txndc Texas Northern District Court txsbk Texas Southern Bankruptcy Court txsdc Texas Southern District Court txwbk Texas Western Bankruptcy Court txwdc Texas Western District Court

utbk Utah Bankruptcy Court utdc Utah District Court

vaebk Virginia Eastern Bankruptcy Court vaedc Virginia Eastern District Court vawbk Virginia Western Bankruptcy Court vawdc Virginia Western District Court vibk Virgin Islands Bankruptcy Court

vidc Virgin Islands District Court vtbk Vermont Bankruptcy Court vtdc Vermont District Court

waebk Washington Eastern Bankruptcy Court waedc Washington Eastern District Court wawbk Washington Western Bankruptcy Court wawdc Washington Western District Court wiebk Wisconsin Eastern Bankruptcy Court wiedc Wisconsin Eastern District Court wiwbk Wisconsin Western Bankruptcy Court wiwdc Wisconsin Western District Court

wvnbk West Virginia Northern Bankruptcy Court wvndc West Virginia Northern District Court wvsbk West Virginia Southern Bankruptcy Court wvsdc West Virginia Southern District Court

wybk Wyoming Bankruptcy Court wydc Wyoming District Court

## <span id="page-64-0"></span>Appendix B: Bankruptcy Chapters

- **7: Chapter 7.** This chapter provides for liquidation, which is the sale of a debtor's nonexempt property and the distribution of the proceeds to creditors.
- **9: Chapter 9.** This chapter provides for reorganization of municipalities, which includes cities/towns, villages, counties, taxing districts, municipal utilities, and school districts.
- **11: Chapter 11.** This chapter generally provides for reorganization, usually involving a corporation or partnership. A chapter 11 debtor usually proposes a plan of reorganization to keep its business alive and pay creditors over time. People in business or individuals can also seek relief in chapter 11.
- **13: Chapter 13.** This chapter provides for debt adjustment of an individual with regular income. Chapter 13 allows a debtor to keep property and pay debts over time, usually three to five years.
- **15: Chapter 15.** This chapter includes ancillary and other cross-border cases. It replaces Chapter 304.
- **304: Chapter 304.** This was replaced by Chapter 15 in 1997.

## <span id="page-65-0"></span>Appendix C: Civil Nature of Suits

- 110 Insurance
- 120 Contract: Marine
- 130 Miller Act
- 140 Negotiable Instrument
- 150 Contract: Recovery/Enforcement
- 151 Contract: Recovery Medicare
- 152 Contract: Recovery Student Loan
- 153 Contract: Recovery Veteran Benefits
- 160 Stockholders Suits
- 190 Contract: Other
- 195 Contract Product Liability
- 196 Contract: Franchise
- 210 Condemnation
- 220 Real Property: Foreclosure
- 230 Rent Lease & Ejectment
- 240 Torts to Land
- 245 Tort Product Liability
- 290 Real Property: Other
- 310 Airplane
- 315 Airplane Product Liability
- 320 Assault Libel & Slander
- 330 Federal Employer's Liability
- 340 Marine
- 345 Marine Product Liability
- 350 Motor Vehicle
- 355 Motor Vehicle Product Liability
- 360 P.I.: Other
- 362 Personal Injury Medical Malpractice
- 365 Personal Injury Product Liability
- 367 TORTS Personal Injury Health Care/Pharmaceutical Personal Injury/Product Liability
- 368 P.I. : Asbestos
- 370 Fraud or Truth-In-Lending
- 371 Truth in Lending
- 375 False Claims Act
- 380 Personal Property: Other
- 385 Prop. Damage Prod. Liability
- 400 State Reapportionment
- 410 Anti-Trust
- 422 Bankruptcy Appeal (801)
- 423 Bankruptcy Withdrawl
- 430 Banks and Banking
- 440 Civil Rights: Other

- 441 Civil Rights: Voting
- 442 Civil Rights: Jobs
- 443 Civil Rights: Accomodations
- 444 Civil Rights: Welfare
- 445 Civil Rights: Americans with Disabilities Employment
- 446 Civil Rights: Americans with Disabilities Other
- 448 Civil Rights: Education
- 450 Commerce ICC Rates, Etc.
- 460 Deportation
- 462 Naturalization Application
- 463 Habeas Corpus Alien Detainee
- 465 Other Immigration Actions
- 470 Racketeer/Corrupt Organization
- 480 Consumer Credit
- 490 Cable/Satellite TV
- 510 Prisoner: Vacate Sentence
- 530 Habeas Corpus (General)
- 535 Death Penalty Habeas Corpus
- 540 Mandamus & Other
- 550 Prisoner: Civil Rights
- 555 Habeas Corpus (Prison Condition)
- 560 Prisoner Petitions Civil Detainee Conditions of Confinement
- 610 Forfeit/Penalty: Agriculture
- 620 Forfeit/Penalty: Food and Drug
- 625 Drug Related Seizure of Property
- 630 Forfeit/Penalty: Liquor Laws
- 640 Forfeit/Penalty: R.R. & Truck
- 650 Forfeit/Penalty: Airline Regulations
- 660 Forfeit/Penalty: Occupational Safety
- 690 Forfeit/Penalty: Other
- 710 Labor: Fair Standards
- 720 Labor: Labor/Management Relations
- 730 Labor: Reporting/Disclosure
- 740 Labor: Railway Labor Act
- 751 Labor: Family and Medical Leave Act
- 790 Labor: Other
- 791 Labor: E.R.I.S.A.
- 810 Selective Service
- 820 Copyright
- 830 Patent
- 840 Trademark
- 850 Securities/Commodities
- 861 Social Security: HIA
- 862 Social Security: Black Lung

- 863 Social Security: DIWC/DIWW
- 864 Social Security: SSID Tit. XVI
- 865 Social Security: RSI Tax Suits
- 870 Taxes
- 871 Tax Suits: IRS-Third Party
- 875 Taxes: Customer Challenge
- 890 Other Statutory Actions
- 891 Agriculture Acts
- 892 Economic Stabilization Act
- 893 Environmental Matters
- 894 Energy Allocation Act
- 895 Freedom of Information Act
- 896 Other Statues Arbitration
- 899 Other Statues Administrative Procedure Act/Review or Appeal of Agency Decision
- 900 Appeal of Fee Determination
- 950 Constitutional State Statute

Other Nature of Suit

## <span id="page-68-0"></span>Appendix D: Appellate Nature of Suits

- 1110 Insurance
- 1120 Marine Contract Actions
- 1130 Miller Act
- 1140 Negotiable Instruments
- 1150 Overpayments & Enforc. of Judgments
- 1151 Overpayments Under Medicare Act
- 1152 Recovery of Defaulted Student Loans
- 1153 Recovery of Ovrpmnts of Vet Benefit
- 1190 Other Contract Actions
- 1195 Contract Product Liability
- 1196 Franchise
- 1210 Land Condemnation
- 1220 Foreclosure
- 1230 Rent, Lease, Ejectment
- 1240 Torts To Land
- 1245 Tort Product Liability
- 1290 Other Real Property Actions
- 1340 Marine Personal Injury
- 1350 Motor Vehicle
- 1360 Other Personal Injury
- 1370 Other Fraud
- 1371 Truth in Lending
- 1380 Other Personal Property Damage
- 1385 Property Damage - Product Liability
- 1410 Antitrust
- 1422 Bankruptcy Appeals Rule 28 USC 158
- 1423 Bankruptcy Withdraw 28 USC 157
- 1430 Banks and Banking
- 1440 Other Civil Rights
- 1441 Civil Rights Voting
- 1442 Civil Rights Jobs
- 1443 Civil Rights Accommodations
- 1444 Civil Rights Welfare
- 1445 American w/Disab.Act -Empl
- 1446 Americans w/Disab Act - Other
- 1450 Interstate Commerce
- 1470 Civil (RICO)
- 1480 Consumer Credit
- 1490 Cable Satellite/TV
- 1610 Agricultural Acts
- 1620 Food and Drugs Acts
- 1625 Drug Related Seizure of Property
- 1630 Liquor Laws

- 1640 Railroad and Trucks
- 1650 Airline Regulations
- 1660 Occupational Safety/Health
- 1690 Other Forfeiture and Penalty Suits
- 1710 Fair Labor Standards Act
- 1720 Labor/Management Relations Act
- 1730 Report & Disclosure
- 1740 Railway Labor Act
- 1790 Other Labor Litigation
- 1791 Employee Retirement
- 1830 Patent
- 1840 Trademark
- 1850 Securities, Commodities, Exchange
- 1862 Black Lung
- 1863 D.I.W.C./D.I.W.W.
- 1870 Tax Suits
- 1871 IRS 3rd Party Suits 26 USC 7609
- 1890 Other Statutory Actions
- 1891 Agricultural Acts
- 1892 Economic Stabilization Act
- 1893 Environmental Matters
- 1950 Constitutionality of State Statutes
- 1990 Other
- 1999 Miscellaneous
- 2110 Insurance
- 2120 Marine Contract Actions
- 2130 Miller Act
- 2140 Negotiable Instruments
- 2150 Ovrpmnts & Enforcement of Judgments
- 2151 Overpayments Under Medicare Act
- 2152 Recovery of Defaulted Student Loans
- 2153 Recovery Overpayment Vet Benefits
- 2190 Other Contract Actions
- 2195 Contract Product Liability
- 2196 Franchise
- 2210 Land Condemnation
- 2220 Foreclosure
- 2230 Rent, Lease, Ejectment
- 2240 Torts to Land
- 2245 Tort Product Liability
- 2290 Other Real Property Actions
- 2310 Airplane Personal Injury
- 2315 Airplane Product Liability
- 2320 Assault, Libel, and Slander

- 2330 Federal Employers' Liability
- 2340 Marine Personal Injury
- 2345 Marine - Product Liability
- 2350 Motor Vehicle
- 2355 Motor Vehicle Product Liability
- 2360 Other Personal Injury
- 2362 Medical Malpractice
- 2365 Personal Injury - Product Liability
- 2368 Asbestos Personal Injury -Product Liability
- 2370 Other Fraud
- 2371 Truth in Lending
- 2380 Other Personal Property Damage
- 2385 Property Damage -Product Liability
- 2410 Antitrust
- 2422 Bankruptcy Appeals Rule 28 USC 158
- 2423 Bankruptcy Withdrawal 28 USC 157
- 2430 Banks and Banking
- 2440 Other Civil Rights
- 2441 Civil Rights Voting
- 2442 Civil Rights Jobs
- 2443 Civil Rights Accommodations
- 2444 Civil Rights Welfare
- 2445 Americans w/Disab.Act -Empl
- 2446 Americans w/Disab Act - Other
- 2450 Interstate Commerce
- 2460 Deportation
- 2462 Naturalization Application
- 2463 Habeas Corpus - Alien Detainee
- 2465 Other Immigration Actions
- 2480 Consumer Credit
- 2490 Cable Satellite/TV
- 2510 Prisoner Petitions - Vacate Sentence
- 2530 Habeas Corpus
- 2535 Habeas Corpus: Death Penalty
- 2540 Prisoner Petitions - Mandamus & Other
- 2550 Prisoner - Civil Rights
- 2555 Prison Condition
- 2610 Agricultural Acts
- 2620 Food and Drug Acts
- 2625 Drug Related Seizure of Property
- 2630 Liquor Laws
- 2640 Railroad and Trucks
- 2650 Airline Regulations
- 2660 Occupational Safety/Health

2690 Other Forfeiture and Penalty Suits

2710 Fair Labor Standards Act

2720 Labor Management Relations Act

2730 Labor/Management Rept & Disclsure

2740 Railway Labor Act

2790 Other Labor Litigation

2791 Employee Retirement

2810 Selective Service

2830 Patent

2850 Securities, Commodities, Exch.

2860 Social Security

2861 Medicare

2862 Black Lung

2863 D.I.W.C./D.I.W.W.

2864 S.S.I.D.

2865 R.S.I.

2870 Tax Suits

2871 IRS 3rd Party Suits 26 USC 7609

2875 Customer Challenge 12 USC 3410

2890 Other Statutory Actions

2891 Agricultural Acts

2892 Economic Stabilization Act

2893 Environmental Matters

2894 Energy Allocation Act

2895 Freedom of Information Act of 1974

2900 Appeal of Fee -Equal Access Justice

2950 Constitutionality of State Statutes

2990 Other

2999 Miscellaneous

3110 Insurance

3120 Marine Contract Actions

3130 Miller Act

3140 Negotiable Instruments

3150 Recovery of Overpayment of Benefits

3151 Overpayments Under Medicare Act

3160 Stockholders' Suits

3190 Other Contract Actions

3196 Franchise

3210 Land Condemnation

3220 Foreclosure

3230 Rent, Lease, Ejectment

3240 Torts to Land

3245 Tort Product Liability

3290 Other Real Property Actions

- 3310 Airplane Personal Injury
- 3315 Airplane Product Liability
- 3320 Assault, Libel, and Slander
- 3330 Federal Employers' Liability
- 3340 Marine Personal Injury
- 3345 Marine - Product Liability
- 3350 Motor Vehicle Personal Injury
- 3355 Motor Vehicle Product Liability
- 3360 Other Personal Injury
- 3365 Personal Injury - Product Liability
- 3368 Asbestos Personal Injury - Product Liability
- 3370 Other Fraud
- 3371 Truth In Lending
- 3380 Other Personal Property Damage
- 3385 Property Damage - Product Liability
- 3400 State Re -Apportionment
- 3410 Antitrust
- 3422 Bankruptcy Appeals Rule 28 USC 158
- 3423 Bankruptcy Withdrawal 28 USC 157
- 3430 Banks and Banking
- 3440 Other Civil Rights
- 3441 Civil Rights Voting
- 3442 Civil Rights Jobs
- 3443 Civil Rights Accommodations
- 3444 Civil Rights Welfare
- 3445 Americans with Disabilities Act - Empl
- 3446 Americans with Disabilities Act - Other
- 3450 Interstate Commerce
- 3460 Deportation
- 3470 Civil (RICO)
- 3480 Consumer Credit
- 3490 Cable Satellite/TV
- 3530 Habeas Corpus
- 3535 Habeas Corpus: Death Penalty
- 3540 Prisoner Petitions -Mandamus & Other
- 3550 Prisoner - Civil Rights
- 3555 Prison Condition
- 3710 Fair Labor Standards Act
- 3720 Labor/Management Relations Act
- 3730 Report & Disclosure
- 3740 Railway Labor Act
- 3790 Other Labor Litigation
- 3791 Employee Retirement
- 3810 Selective Service

3820 Copyright

3830 Patent

3840 Trademark

3850 Securities, Commodities, Exch.

3890 Other Statutory Actions

3891 Agricultural Acts

3892 Economic Stabilization Act

3893 Environmental Matters

3894 Energy Allocation Act

3895 Freedom of Information Act of 1974

3950 Constitutionality of State Statutes

3990 Other

3999 Miscellaneous

4110 Insurance

4120 Marine Contract Actions

4140 Negotiable Instruments

4150 Overpayments & Enforcement of Judgments

4160 Stockholders Suits

4190 Other Contract Actions

4195 Contract Product Liability

4196 Franchise

4210 Land Condemnation

4220 Foreclosure

4230 Rent, Lease, Ejectment

4240 Torts to Land

4245 Tort Product Liability

4290 Other Real Property Actions

4310 Airplane Personal Injury

4315 Airplane Product Liability

4320 Assault, Libel, and Slander

4340 Marine Personal Injury

4345 Marine - Product Liability

4350 Motor Vehicle Personal Injury

4355 Motor Vehicle Product Liability

4360 Other Personal Injury

4362 Medical Malpractice

4365 Personal Injury - Product Liability

4368 Asbestos Personal Injury - Product Liability

4370 Other Fraud

4371 Truth in Lending

4380 Other Personal Property Damage

4385 Property Damage - Product Liability

4440 Other Civil Rights

4441 Civil Rights Voting

4442 Civil Rights Jobs

4443 Civil Rights Accommodations

4444 Civil Rights Welfare

4445 Americans with Disabilities Act - Empl

4446 Americans with Disabilities Act - Other

4470 Civil (RICO)

4480 Consumer Credit

4490 Cable Satellite/TV

4555 Prisoner- Prison Condition

4990 Other

4999 Miscellaneous

5535 Habeas Corpus: Death Penalty

5990 Other

5992 Local Jurisdictional Appeal

4950 Constitutionality of State Statutes

1894 Energy Allocation Act

Other Nature of Suit

## <span id="page-75-0"></span>Appendix E: Search Regions in Production

Valid search regions vary by environment. The following tables show the regions in Production.

**NOTE:** For a current list of courts in QA, please visit: <https://qa-pcl.uscourts.gov/pcl/pages/courtInformation.jsf>

### **Search Regions in Production**

| Region | Region Name          |
|--------|----------------------|
| Code   |                      |
| 01     | First Circuit        |
| 02     | Second Circuit       |
| 03     | Third Circuit        |
| 04     | Fourth Circuit       |
| 05     | Fifth Circuit        |
| 06     | Sixth Circuit        |
| 07     | Seventh Circuit      |
| 08     | Eighth Circuit       |
| 09     | Ninth Circuit        |
| 10     | Tenth Circuit        |
| 11     | Eleventh Circuit     |
| cafc   | Federal Circuit      |
| dcca   | D.C. Circuit         |
| al     | Alabama              |
| alm    | Alabama Middle       |
| aln    | Alabama Northern     |
| als    | Alabama Southern     |
| ak     | Alaska               |
| az     | Arizona              |
| ar     | Arkansas             |
| are    | Arkansas Eastern     |
| arw    | Arkansas Western     |
| ca     | California           |
| cac    | California Central   |
| cae    | California Eastern   |
| can    | California Northern  |
| cas    | California Southern  |
| cofc   | Federal Claims       |
| co     | Colorado             |
| ct     | Connecticut          |
| dc     | District of Columbia |
| de     | Delaware             |
| fl     | Florida              |
| flm    | Florida Middle       |
| fln    | Florida Northern     |
| fls    | Florida Southern     |

| ga  | Georgia              |
|-----|----------------------|
| gam | Georgia Middle       |
| gan | Georgia Northern     |
| gas | Georgia Southern     |
| gu  | Guam                 |
| hi  | Hawaii               |
| id  | Idaho                |
| il  | Illinois             |
| ilc | Illinois Central     |
| iln | Illinois Northern    |
|     |                      |
| ils | Illinois Southern    |
| in  | Indiana              |
| inn | Indiana Northern     |
| ins | Indiana Southern     |
| ia  | Iowa                 |
| ian | Iowa Northern        |
| ias | Iowa Southern        |
| ks  | Kansas               |
| ky  | Kentucky             |
| kye | Kentucky Eastern     |
| kyw | Kentucky Western     |
| la  | Louisiana            |
| lae | Louisiana Eastern    |
| lam | Louisiana Middle     |
| law | Louisiana Western    |
| me  | Maine                |
| md  | Maryland             |
| ma  | Massachusetts        |
| mi  | Michigan             |
| mie | Michigan Eastern     |
| miw | Michigan Western     |
| mn  | Minnesota            |
| ms  | Mississippi          |
| msn | Mississippi Northern |
| mss | Mississippi Southern |
| mo  | Missouri             |
| moe | Missouri Eastern     |
| mow | Missouri Western     |
| mt  | Montana              |
| ne  | Nebraska             |
| nv  | Nevada               |
| nh  | New Hampshire        |
| nj  | New Jersey           |
| nm  | New Mexico           |
| ny  | New York             |
| nye | New York Eastern     |
|     |                      |

| nyn | New York Northern        |
|-----|--------------------------|
| nys | New York Southern        |
| nyw | New York Western         |
| nc  | North Carolina           |
| nce | North Carolina Eastern   |
| ncm | North Carolina Middle    |
| ncw | North Carolina Western   |
| nd  | North Dakota             |
| nmi | Northern Mariana Islands |
| oh  | Ohio                     |
| ohn | Ohio Northern            |
| ohs | Ohio Southern            |
| ok  | Oklahoma                 |
|     |                          |
| oke | Oklahoma Eastern         |
| okn | Oklahoma Northern        |
| okw | Oklahoma Western         |
| or  | Oregon                   |
| pa  | Pennsylvania             |
| pae | Pennsylvania Eastern     |
| pam | Pennsylvania Middle      |
| paw | Pennsylvania Western     |
| pr  | Puerto Rico              |
| ri  | Rhode Island             |
| sc  | South Carolina           |
| sd  | South Dakota             |
| tn  | Tennessee                |
| tne | Tennessee Eastern        |
| tnm | Tennessee Middle         |
| tnw | Tennessee Western        |
| tx  | Texas                    |
| txe | Texas Eastern            |
| txn | Texas Northern           |
| txs | Texas Southern           |
| txw | Texas Western            |
| ut  | Utah                     |
| vt  | Vermont                  |
| vi  | Virgin Islands           |
| va  | Virginia                 |
| vae | Virginia Eastern         |
| vaw | Virginia Western         |
| wa  | Washington               |
| wae | Washington Eastern       |
| waw | Washington Western       |
| wv  | West Virginia            |
|     |                          |
| wvn | West Virginia Northern   |
| wvs | West Virginia Southern   |

| wi  | Wisconsin         |
|-----|-------------------|
| wie | Wisconsin Eastern |
| wiw | Wisconsin Western |
| Wy  | Wyoming           |

## <span id="page-79-0"></span>Appendix F: Case Types

Case type codes are created and assigned by individual courts. This list includes the most commonly used case type codes. These codes are not defined by the PACER Service Center, as their meanings can vary from court to court.

| 1453c | bkp   | dcrim | ml     | po    | tp  |
|-------|-------|-------|--------|-------|-----|
| 158d  | cafc  | dm    | mp     | pr    | usc |
| 2255  | civil | dp    | mr     | prici | usp |
| 23f   | cm    | dpw   | ms     | prsw  | vv  |
| ag    | cr    | hc    | msop   | prswo | xc  |
| agen  | crim  | hc.st | mv     | prus  |     |
| agpet | ct    | img   | ncrim  | pt    |     |
| ap    | cv    | ins   | ohndca | r5.dc |     |
| bail  | cv.pr | mand  | op     | rj    |     |
| bap   | cv.us | mc    | opus   | rvw   |     |
| bk    | cvpri | md    | other  | rvw.i |     |
| bkcy  | cvrgt | misc  | pcd    | stp   |     |
| bkd   | cvus  | mj    | pcf    | tax   |     |

## <span id="page-80-0"></span>Appendix G: Response Codes

For the REST services, response codes are defined by the Java Enterprise Edition (EE) 7 specification.

Errors handled by the server can use any of the following codes: https://docs.oracle.com/javaee/7/api/javax/ws/rs/core/Response.Status.html

For the application, these response codes are used for the following conditions:

- 200 Ok: The request has succeeded. The meaning of the success depends on the HTTP method.
  - o GET: The resource has been fetched and is transmitted in the message body.
  - o HEAD: The entity headers are in the message body.
  - o PUT or POST: The resource describing the result of the action is transmitted in the message body.
- 204 No Content: There is no content to send for this request, but the headers may be useful. The user-agent may update its cached headers for this resource with the new ones.
- 400 Bad Request: HttpStatus.BAD\_REQUEST
  - 400 Invalid Argument: HttpStatus.BAD\_REQUEST
  - 400 Report Running Exception: HttpStatus.BAD\_REQUEST
  - 400 Stopped Exception: HttpStatus.BAD\_REQUEST
  - The server could not understand the request due to invalid syntax.
- 401 Unauthorized user: HttpStatus.UNAUTHORIZED Although the HTTP standard specifies "unauthorized," semantically this response means "unauthenticated." That is, the client must authenticate itself to get the requested response.
- 404 Report Not Found: HttpStatus.NOT\_FOUND The server cannot find the requested resource. In the browser, this means the URL is not recognized. In an API, this can also mean that the endpoint is valid but the resource itself does not exist. Servers may also send this response instead of 403 to hide the existence of a resource from an unauthorized client. This response code is probably the most famous one due to its frequent occurrence on the web.
- 406 Validation Exception: HttpStatus.NOT\_ACCEPTABLE This response is sent when the web server, after performing server-driven content negotiation, does not find any content that conforms to the criteria given by the user agent.
- 429 Too Many Reports Running: HttpStatus.TOO\_MANY\_REQUESTS The user has sent too many requests in a given amount of time ("rate limiting").
- 500 Report failed: HttpStatus.INTERNAL\_SERVER\_ERROR 500 All Other Exceptions: HttpStatus.INTERNAL\_SERVER\_ERROR The server has encountered a situation it does not know how to handle.