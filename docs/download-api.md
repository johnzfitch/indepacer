# **PACER Case Locator (PCL) Application Programming Interface (API) User Guide**

**November 2024**

## **Contents**

| Overview                          | 4    |
| --------------------------------- | ---- |
| Public Environments               | 4    |
| Schema                            | 4    |
| Quick Start                       | 5    |
| PACER Authentication API          | 6    |
| Search Tools                      | 6    |
| Immediate Searches                | 6    |
| Case and Party Search Examples    | 9    |
| Immediate Searches                | 9    |
| Case Search – JSON                | 9    |
| Case Search – XML                 | 11   |
| Party Search - JSON               | 13   |
| Party Search - XML                | 17   |
| Advanced Searches                 | 21   |
| Batch Searches                    | 28   |
| Batch Search Examples             | 33   |
| Start a Batch Case Search - JSON  | 33   |
| Start Batch Case Search - XML     | 34   |
| Get Batch Job Status - JSON       | 34   |
| Get Batch Job Status - XML        | 35   |
| Get List of Batch Jobs – JSON     | 36   |
| Get List of Batch Jobs – XML      | 37   |
| Get Batch Job Results - JSON      | 38   |
| Get Batch Job Results - XML       | 38   |
| PCL Search API                    | 40   |
| Setting the Headers               | 40   |
| API Endpoints                     | 41   |
| Basic Searches                    | 41   |
| Batch Jobs                        | 41   |
| Search Criteria—Data Definitions  | 44   |
| Case Searches – Searchable Fields | 44   |

| Case Search – JSON Representation         | Case Search – XML Representation  | 47   |
| ----------------------------------------- | --------------------------------- | ---- |
|                                           |                                   | 47   |
| Party Searches – Searchable Fields        |                                   | 48   |
| Party Search – JSON Representation        | Party Search – XML Representation | 52   |
| Search Results—Data Definitions           |                                   | 53   |
| Case Search Results                       |                                   | 53   |
| Party Search Results                      |                                   | 56   |
| Sorting                                   |                                   | 59   |
| Sortable Case Fields                      |                                   | 59   |
| Sortable Party Fields                     |                                   | 59   |
| Pagination                                |                                   | 59   |
| Appendix A: Court IDs                     |                                   | 60   |
| Appendix B: Bankruptcy Chapters           |                                   | 65   |
| Appendix C: Civil Nature of Suits         |                                   | 66   |
| Appendix D: Appellate Nature of Suits     |                                   | 69   |
| Appendix E: Search Regions in Production. |                                   | 76   |
| Appendix F: Case Types                    |                                   | 80   |
| Appendix G: Response Codes                |                                   | 81   |

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
| -------------------- | ----------------- | --------------------- | ------------------------ |
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

|                  | ALL COURT TYPES |                                                           |                                                              |      |
| ---------------- | --------------- | --------------------------------------------------------- | ------------------------------------------------------------ | ---- |
| API Field(s)     | Type            | Description                                               | Format                                                       |      |
| jurisdictionType | String          | Jurisdiction type of the case                             | •<br>ap for appellate cases<br>•<br>bk for bankruptcy cases<br>•<br>cr for criminal cases<br>•<br>cv for civil cases<br>•<br>mdl for Judicial Panel Multidistrict Litigation (JPML)<br>cases |      |
| caseId           | Integer         | Sequentially generated number that<br>identifies the case | Integer maximum: 2,147,483,647                               |      |
| caseNumberFull   | String          | Case number                                               | When all elements are present in the case number, the<br>most common format is<br>o:yy-tp-nnnnn, where "o" is a<br>single-digit integer that specifies the office and "tp" is<br>the two-character case type.<br>Users may or may not have all of the elements of the<br>case number, so the following formats should be<br>accepted:<br>•<br>yy-nnnnn<br>•<br>yy-tp-nnnnn<br>•<br>yy tp nnnnn<br>•<br>yytpnnnnn<br>•<br>o:yy-nnnnn<br>•<br>o:yy-tp-nnnnn<br>•<br>o:yy tp nnnnn<br>•<br>o:yytpnnnnn |      |

| caseTitle                                               | String       | The title by which the case is commonly<br>known             | Text field that is not case-sensitive and accepts<br>alphanumeric and special characters.<br>Maximum length: 254 |
| ------------------------------------------------------- | ------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| caseOffice                                              | String       | The divisional office in which the case<br>was filed         | One alphanumeric character                                   |
| caseNumber                                              | String       | The sequence number of the case                              | Five-digit number                                            |
| caseType                                                | List[String] | Code that identifies the type of case                        | Text field that accepts letters, numbers, and special<br>characters.<br>Maximum length: 6 |
| caseYear                                                | String       | The last two digits of the year in which<br>the case was filed | Two-digit or four-digit year                                 |
| courtId                                                 | List[String] | The general geographical region or<br>specific court district | The court ID is the abbreviation of the court location<br>combined with the court type (dc or bk).<br>Maximum length: 6 characters<br>For a complete list of valid court IDs and regions, see<br>Appendix A. More information about the role and<br>structure of the U.S. courts can be found here:<br>https://www.uscourts.gov/about-federal-courts/court<br>role-and-structure. |
| dateFiledFrom and<br>dateFiledTo                        | Date         | Filing date of the case, generated during<br>case opening    | Date in the format yyyy-MM-dd                                |
| effectiveDateClosedFrom<br>and<br>effectiveDateClosedTo | Date         | Filing date of the most recent docket<br>entry that terminated (closed) the case<br>(if a case was closed and reopened,<br>there could have been multiple<br>terminations) | Date in the format yyyy-MM-dd                                |
|                                                         |              | BANKRUPTCY CASES ONLY                                        |                                                              |
| API Field(s)                                            | Type         | Description                                                  | Format                                                       |
| federalBankruptcyChapter                                | List[String] | Federal bankruptcy chapter under<br>which the case is filed  | •<br>7: Chapter 7<br>•<br>9: Chapter 9<br>•<br>11: Chapter 11<br>•<br>13: Chapter 13<br>•<br>15: Chapter 15 |

|                        |              |                                         | •<br>304: Chapter 304                                   |
| ---------------------- | ------------ | --------------------------------------- | ------------------------------------------------------- |
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

| PARTY SEARCH INPUT OPTIONS |              |                                                              |                                                              |      |
| -------------------------- | ------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ---- |
| API Field(s)               | Type         | Description                                                  | Format                                                       |      |
| reportId                   | String       | User-supplied identifier that is returned with<br>search results | This field has no effect on the search or the results of<br>the search but is useful for identifying a search. |      |
| courtId                    | List[String] | The geographical region or specific court<br>district        | See Appendix E<br>for a list of valid regions for each<br>environment. |      |
| caseId                     | Integer      | A unique identifier for each case                            |                                                              |      |
| caseNumberFull             | String       | A formatted case number                                      | Case numbers may be entered in each of the<br>following formats:<br>•<br>yy-nnnnn<br>•<br>yy-tp-nnnnn |      |
|                            |              |                                                              | •<br>yy tp nnnnn                                             |      |
|                            |              |                                                              | •<br>yytpnnnnn                                               |      |
|                            |              |                                                              | •<br>o:yy-nnnnn                                              |      |
|                            |              |                                                              | •<br>o:yy-tp-nnnnn                                           |      |
|                            |              |                                                              | •<br>o:yy tp nnnnn                                           |      |
|                            |              |                                                              | •<br>o:yytpnnnnn                                             |      |
|                            |              |                                                              | where:<br>"yy"<br>is case year (may be 2 or 4 digits)<br>"nnnn"<br>is case number (up to 5 digits)<br>"tp"<br>is case type (up to 2 characters)<br>"o"<br>is the office where the case was filed (1 digit)<br>NOTE:<br>Case type and office values are ignored for<br>appellate case numbers. |      |
| lastName                   | String       | The last name of a party to search. This field<br>is also used to search for a non-person entity.<br>If the exactMatches<br>flag is not set to "true,"<br>the lastName parameter is a "starts with"<br>search parameter that will match any last<br>name that starts with the included characters. | Alphanumeric value of last name                              |      |
| firstName                  | String       | The first name of a party to search.                         | Alphanumeric value of first name                             |      |

|                |              | If the exactMatches<br>flag is not set, the<br>lastName parameter is a "starts with"<br>search<br>parameter that will match any last name that<br>starts with the included characters. |                                                              |
| -------------- | ------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| middleName     | String       | The middle name of a party to search.                        | Alphanumeric value of middle name                            |
|                |              | If the exactMatches<br>flag is not set, the<br>lastName parameter is a "starts with"<br>search<br>parameter that will match any last name that<br>starts with the included characters. |                                                              |
| generation     | String       | The name suffix (e.g., III, MD)                              | String length maximum: 5                                     |
|                |              | This is an exact match field for length and<br>capitalization. |                                                              |
| partyType      | String       | The court-assigned party type for a party<br>involved in a case | Party type codes are created and assigned by<br>individual courts, and as such, their meanings can vary<br>from court to court. |
| role           | List[String] | The court-assigned role for a party to a case                | Party role codes are created and assigned by individual<br>courts, and as such, their meanings can vary from<br>court to court. |
|                |              |                                                              | NOTE:<br>Because the PCL does not receive party role<br>information for appellate cases, a search including<br>party roles will not return appellate cases, even if the<br>search would have returned appellate cases if the role<br>had been omitted. |
| exactNameMatch | Boolean      | By default, any party name value provided<br>will return any party whose name starts with<br>that value. | {<br>"lastName": "Smith",<br>"exactNameMatch": true<br>}     |
|                |              | Set exactNameMatch<br>to "true" to override<br>that behavior and return only names that<br>exactly match what is entered. |                                                              |

| caseYearFrom     | Integer | Limit results to those of cases from the year<br>specified and later | 4-digit integer value maximum                                |
| ---------------- | ------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| caseYearTo       | Integer | Limit results to those of cases from the year<br>specified and earlier | 4-digit integer value maximum                                |
| jurisdictionType | String  |                                                              | The most common jurisdiction types are:<br>•<br>ap<br>for appellate cases<br>•<br>bk<br>for bankruptcy cases<br>•<br>cr<br>for criminal cases<br>•<br>cv<br>for civil cases<br>•<br>mdl<br>for Judicial Panel Multidistrict Litigation<br>(JPML) cases |
| ssn              | String  | Search for parties with a particular SSN.                    | See Appendix F<br>for a complete list of known valid<br>case types for each environment.<br>Must be all-numeric values; may include dashes but |
|                  |         |                                                              | not required.<br>When specified, a last name/entity name must also be<br>specified. |
| ssn4             | String  | Search for parties whose SSN ends with a<br>specified four digits. | When specified, a last name/entity name must also be<br>specified. |

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

