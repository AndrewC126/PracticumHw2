SELECT 
    dt.defect_code,
    COUNT(DISTINCT dr.lot_id) AS lot_count,
    COUNT(DISTINCT dr.reporting_week) AS week_count,
    SUM(dr.quantity_of_defects) AS total_quantity,
    CASE 
        WHEN COUNT(DISTINCT dr.lot_id) > 1 AND COUNT(DISTINCT dr.reporting_week) > 1 THEN 'RECURRING'
        WHEN COUNT(DISTINCT dr.lot_id) = 1 THEN 'ONE-OFF'
        ELSE 'INSUFFICIENT DATA'
    END AS classification_logic
FROM defect_types dt
LEFT JOIN defect_records dr ON dt.defect_type_id = dr.defect_type_id
WHERE dr.quantity_of_defects > 0  -- AC3: Exclude 0 qty
GROUP BY dt.defect_code
ORDER BY lot_count DESC, total_quantity DESC; -- AC9: Default sorting

SELECT 
    dt.defect_code,
    l.lot_number,
    l.production_date,
    dr.quantity_of_defects,
    dr.reporting_week || '/' || dr.reporting_year AS period
FROM defect_records dr
JOIN defect_types dt ON dr.defect_type_id = dt.defect_type_id
JOIN lots l ON dr.lot_id = l.lot_id
WHERE dt.defect_code = 'D-001' -- Replace with dynamic parameter
ORDER BY l.production_date ASC;

SELECT 
    defect_code,
    'Missing reporting periods or quantities' AS missing_info_msg
FROM defect_types dt
WHERE NOT EXISTS (
    SELECT 1 
    FROM defect_records dr 
    WHERE dr.defect_type_id = dt.defect_type_id 
    AND dr.quantity_of_defects > 0
);
