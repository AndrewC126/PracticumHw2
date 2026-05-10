-- -----------------------------------------------------
-- Table: defect_types
-- -----------------------------------------------------
CREATE TABLE defect_types (
    defect_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    defect_code TEXT NOT NULL,
    classification TEXT NOT NULL, -- Recurring vs One-off
    status TEXT NOT NULL,         -- e.g., Insufficient Data, Active
    CONSTRAINT uq_defect_code UNIQUE (defect_code)
);

-- -----------------------------------------------------
-- Table: lots
-- -----------------------------------------------------
CREATE TABLE lots (
    lot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lot_number TEXT NOT NULL,
    production_date DATE NOT NULL,
    week_number INTEGER NOT NULL,
    CONSTRAINT uq_lot_number UNIQUE (lot_number),
    CONSTRAINT ck_week_range CHECK (week_number >= 1 AND week_number <= 53)
);

-- -----------------------------------------------------
-- Table: defect_records
-- -----------------------------------------------------
CREATE TABLE defect_records (
    defect_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    defect_type_id BIGINT NOT NULL,
    lot_id BIGINT NOT NULL,
    quantity_of_defects INTEGER NOT NULL,
    reporting_week INTEGER NOT NULL,
    reporting_year INTEGER NOT NULL,
    
    -- Relationships
    CONSTRAINT fk_defect_type FOREIGN KEY (defect_type_id) 
        REFERENCES defect_types(defect_type_id) ON DELETE CASCADE,
    CONSTRAINT fk_lot FOREIGN KEY (lot_id) 
        REFERENCES lots(lot_id) ON DELETE CASCADE,
    
    -- Business Rules & Ranges
    CONSTRAINT ck_qty_non_negative CHECK (quantity_of_defects >= 0),
    CONSTRAINT ck_reporting_week CHECK (reporting_week >= 1 AND reporting_week <= 53),
    
    -- Ensure uniqueness to prevent duplicate reporting for the same defect on the same lot
    CONSTRAINT uq_defect_per_lot UNIQUE (defect_type_id, lot_id)
);

-- Indexes for performance (AC9)
CREATE INDEX idx_defect_records_type ON defect_records(defect_type_id);
CREATE INDEX idx_defect_records_lot ON defect_records(lot_id);
