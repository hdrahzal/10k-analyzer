"use client";

import { useCallback, useState } from "react";
import { FileText, Upload } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";

// Sample 10-K content for testing
const SAMPLE_DOCUMENT_CONTEXT = `[Page 1]
UNITED STATES SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549
FORM 10-K
ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934
For the fiscal year ended December 31, 2024
Commission File Number: 001-12345
ACME TECHNOLOGY CORPORATION
(Exact name of registrant as specified in its charter)
Delaware (State of incorporation) 12-3456789 (I.R.S. Employer Identification No.)
100 Innovation Drive, San Francisco, California 94105

---

[Page 5]
PART I
Item 1. Business
Overview
ACME Technology Corporation ("ACME," "we," "us," or "our") is a global technology company that designs, develops, and sells consumer electronics, computer software, and online services. We are headquartered in San Francisco, California, and employ approximately 45,000 people worldwide.

Our principal products include:
- SmartPhone Pro series - our flagship mobile device line
- CloudSync software platform - enterprise cloud solutions
- AI Assistant services - artificial intelligence powered digital assistants
- TechWear wearable devices - smartwatches and fitness trackers

---

[Page 12]
Item 1A. Risk Factors
Investing in our common stock involves a high degree of risk. You should carefully consider the following risk factors before making an investment decision.

RISKS RELATED TO OUR BUSINESS
Competition Risk: We operate in highly competitive markets. Our competitors include established technology companies with greater financial resources, such as GlobalTech Inc. and MegaSoft Corporation. Increased competition could result in pricing pressures, reduced market share, and decreased profitability.

Supply Chain Risk: We rely on third-party manufacturers, primarily located in Asia, to produce our hardware products. Disruptions to our supply chain, including natural disasters, pandemics, or geopolitical events, could materially impact our ability to meet customer demand.

Cybersecurity Risk: Our business depends on the security of our systems and data. A significant cybersecurity breach could damage our reputation and result in substantial financial losses.

---

[Page 28]
Item 6. Selected Financial Data
The following table presents selected consolidated financial data for the five fiscal years ended December 31, 2024.

(in millions, except per share data)
                                2024        2023        2022        2021        2020
Net Revenue                   $48,500     $42,300     $38,100     $35,200     $31,800
Gross Profit                  $19,400     $16,920     $14,478     $13,024     $11,448
Operating Income              $12,125     $10,575      $9,525      $8,800      $7,950
Net Income                     $9,700      $8,460      $7,620      $7,040      $6,360
Earnings Per Share (Diluted)    $4.85       $4.23       $3.81       $3.52       $3.18
Total Assets                  $85,000     $78,500     $72,000     $66,000     $60,500
Long-term Debt                $15,000     $14,000     $13,000     $12,000     $11,000
Stockholders' Equity          $52,000     $48,000     $44,000     $40,500     $37,000

---

[Page 35]
Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations

Overview
Fiscal year 2024 was a record year for ACME Technology Corporation. We achieved net revenue of $48.5 billion, representing a 14.7% increase from fiscal year 2023. This growth was primarily driven by strong demand for our SmartPhone Pro 15 series and continued expansion of our CloudSync enterprise platform.

Revenue by Segment:
- Consumer Devices: $28.2 billion (58% of total revenue), up 12% YoY
- Software & Services: $14.5 billion (30% of total revenue), up 22% YoY  
- Wearables & Accessories: $5.8 billion (12% of total revenue), up 8% YoY

Geographic Revenue Distribution:
- Americas: $21.8 billion (45%)
- Europe, Middle East & Africa: $13.1 billion (27%)
- Asia Pacific: $13.6 billion (28%)

---

[Page 42]
Liquidity and Capital Resources
As of December 31, 2024, we had cash, cash equivalents, and marketable securities totaling $22.5 billion, compared to $19.8 billion at December 31, 2023. We believe our existing cash balances, combined with cash generated from operations, will be sufficient to meet our operational needs and capital expenditure requirements for at least the next twelve months.

Cash Flow Summary (in millions):
Cash provided by operating activities: $14,200
Cash used in investing activities: ($6,800)
Cash used in financing activities: ($4,700)
Net increase in cash: $2,700

Capital Expenditures: We invested $5.2 billion in capital expenditures during fiscal 2024, primarily for manufacturing equipment, data center infrastructure, and research facilities.

---

[Page 58]
Item 8. Financial Statements and Supplementary Data

CONSOLIDATED BALANCE SHEET
As of December 31, 2024 and 2023 (in millions)

ASSETS                                          2024        2023
Current Assets:
  Cash and cash equivalents                   $12,500     $10,800
  Marketable securities                       $10,000      $9,000
  Accounts receivable, net                     $8,200      $7,400
  Inventories                                  $4,800      $4,200
  Other current assets                         $2,500      $2,100
Total Current Assets                          $38,000     $33,500

Property and equipment, net                   $18,000     $16,500
Goodwill and intangible assets                $12,000     $11,500
Other long-term assets                        $17,000     $17,000
Total Assets                                  $85,000     $78,500

---

[Page 72]
Item 9A. Controls and Procedures
Evaluation of Disclosure Controls and Procedures
Our management, with the participation of our Chief Executive Officer and Chief Financial Officer, has evaluated the effectiveness of our disclosure controls and procedures as of December 31, 2024. Based on this evaluation, our CEO and CFO concluded that our disclosure controls and procedures were effective as of December 31, 2024.

Management's Report on Internal Control Over Financial Reporting
Our management is responsible for establishing and maintaining adequate internal control over financial reporting. Management assessed the effectiveness of our internal control over financial reporting as of December 31, 2024, based on criteria established in Internal Control—Integrated Framework (2013) issued by COSO. Based on this assessment, management concluded that our internal control over financial reporting was effective as of December 31, 2024.

---

[Page 85]
PART III
Item 10. Directors, Executive Officers and Corporate Governance

Executive Officers:
- Sarah Chen, Chief Executive Officer (Age 52) - CEO since 2019, previously COO
- Michael Rodriguez, Chief Financial Officer (Age 48) - CFO since 2021
- Dr. James Park, Chief Technology Officer (Age 45) - CTO since 2020
- Lisa Thompson, Chief Operating Officer (Age 50) - COO since 2022
- David Kim, General Counsel (Age 55) - General Counsel since 2018

Board of Directors:
The Board consists of 9 members, 7 of whom are independent directors. Sarah Chen serves as Chair of the Board.`;

const SAMPLE_FILE_NAME = "ACME_Technology_10K_2024.pdf";

interface UploadDropzoneProps {
  onFileProcessed: (documentContext: string, fileName: string) => void;
}

export function UploadDropzone({ onFileProcessed }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      if (file.type !== "application/pdf") {
        setError("Please upload a PDF file");
        return;
      }

      setIsProcessing(true);
      setError(null);

      try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch("/api/upload", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.error || "Failed to process PDF");
        }

        const data = await response.json();

        // Format chunks into context string
        const contextString = data.document.chunks
          .map(
            (chunk: { pageNumber: number; text: string }) =>
              `[Page ${chunk.pageNumber}]\n${chunk.text}`
          )
          .join("\n\n---\n\n");

        onFileProcessed(contextString, data.document.fileName);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to process PDF");
      } finally {
        setIsProcessing(false);
      }
    },
    [onFileProcessed]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile]
  );

  if (isProcessing) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <Spinner className="h-8 w-8 text-primary" />
        <div className="text-center">
          <p className="text-lg font-medium text-foreground">
            Processing your 10-K...
          </p>
          <p className="text-sm text-muted-foreground">
            Extracting and analyzing document content
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          10-K/Q Analyzer
        </h1>
        <p className="mt-2 max-w-md text-muted-foreground">
          Upload a 10-K/Q filing to start analyzing. You can then ask our dedicated chatbot about the filing you&apos;ve uploaded.
        </p>
      </div>

      <label
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          flex w-full max-w-lg cursor-pointer flex-col items-center justify-center gap-4 
          rounded-xl border-2 border-dashed p-12 transition-all
          ${
            isDragging
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-muted/50"
          }
        `}
      >
        <input
          type="file"
          accept=".pdf"
          onChange={handleInputChange}
          className="hidden"
        />

        <div
          className={`rounded-full p-4 transition-colors ${
            isDragging ? "bg-primary/10" : "bg-muted"
          }`}
        >
          {isDragging ? (
            <FileText className="h-8 w-8 text-primary" />
          ) : (
            <Upload className="h-8 w-8 text-muted-foreground" />
          )}
        </div>

        <div className="text-center">
          <p className="font-medium text-foreground">
            {isDragging ? "Drop your PDF here" : "Drag & drop your 10-K PDF"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            or click to browse files
          </p>
        </div>
      </label>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      <div className="flex items-center gap-4">
        <div className="h-px flex-1 bg-border" />
        <span className="text-sm text-muted-foreground">or</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <Button
        variant="outline"
        onClick={() => onFileProcessed(SAMPLE_DOCUMENT_CONTEXT, SAMPLE_FILE_NAME)}
        className="gap-2"
      >
        <FileText className="h-4 w-4" />
        Use Sample 10-K (ACME Technology)
      </Button>
    </div>
  );
}
