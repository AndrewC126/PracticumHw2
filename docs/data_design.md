## Defect Type
Defect Code (Primary Key)
Description
Classification (Recurring vs. One-off)
Status (e.g., Insufficient Data, Active)

## Lot
Lot ID (Primary Key)
Lot Number
Production Date
Week Number

## Defect Record
Record ID (Primary Key)
Defect Code (Foreign Key)
Lot ID (Foreign Key)
Quantity of Defects
Reporting Period (Week/Year)

## Relationships
One Defect Type can have many Defect Records.
One Lot can have many Defect Records.

```mermaid
erDiagram

    DEFECT_TYPE {
        string Defect_Code PK
        string Description
        string Classification
        string Status
    }

    LOT {
        string Lot_ID PK
        string Lot_Number
        date Production_Date
        int Week_Number
    }

    DEFECT_RECORD {
        string Record_ID PK
        string Defect_Code FK
        string Lot_ID FK
        int Quantity_of_Defects
        string Reporting_Period
    }

    DEFECT_TYPE ||--o{ DEFECT_RECORD : has
    LOT ||--o{ DEFECT_RECORD : contains
