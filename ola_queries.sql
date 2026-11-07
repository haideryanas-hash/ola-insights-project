-- =====================================================================
--  OLA RIDE INSIGHTS  |  SQL QUERIES  (table: rides)
--  Source: ola_clean.csv.gz  (output of clean_data.py, 103,024 rows)
--
--  Works as-is in SQLite and MySQL. For SQL Server replace
--  "LIMIT 5" with "SELECT TOP 5 ..." .
--
--  HOW TO LOAD THE DATA
--   * DB Browser for SQLite : File > Import > Table from CSV (ola_clean_for_powerbi.csv), name it  rides
--   * MySQL Workbench       : right-click schema > Table Data Import Wizard > pick the CSV, name it  rides
--
--  COLUMN NAMES (cleaned)  -> original name in raw Excel
--   Customer_Cancel_Reason -> Canceled_Rides_by_Customer
--   Driver_Cancel_Reason   -> Canceled_Rides_by_Driver
--   Driver_Rating          -> Driver_Ratings
--   Vehicle_Type 'E-Bike'  -> 'eBike'
--   'Not Applicable' replaces blanks in text columns (cancelled rides have no payment/reason)
-- =====================================================================


-- Q1. Retrieve all successful bookings
-- Result: 63,967 rows
SELECT *
FROM rides
WHERE Booking_Status = 'Success';


-- Q2. Average ride distance for each vehicle type (completed rides)
-- Result: E-Bike 25.15 | Prime Plus 25.03 | Prime Sedan 25.01 | Mini 24.98 | Bike 24.93 | Prime SUV 24.88 | Auto 10.04
SELECT Vehicle_Type,
       ROUND(AVG(Ride_Distance), 2) AS avg_distance_km
FROM rides
WHERE Booking_Status = 'Success'
GROUP BY Vehicle_Type
ORDER BY avg_distance_km DESC;


-- Q3. Total number of cancelled rides by customers
-- Result: 10,499
SELECT COUNT(*) AS cancelled_by_customer
FROM rides
WHERE Booking_Status = 'Canceled by Customer';


-- Q4. Top 5 customers with the highest number of rides
-- Result: CID954071 (5 rides), then four customers with 4 rides each.
-- Many customers tie at 4 rides, so total booking value is used as the tie-breaker.
SELECT Customer_ID,
       COUNT(*)           AS total_rides,
       SUM(Booking_Value) AS total_booking_value
FROM rides
GROUP BY Customer_ID
ORDER BY total_rides DESC, total_booking_value DESC
LIMIT 5;


-- Q5. Rides cancelled by drivers due to personal and car-related issues
-- Result: 6,542
SELECT COUNT(*) AS personal_car_issue_cancellations
FROM rides
WHERE Driver_Cancel_Reason = 'Personal & Car related issue';


-- Q6. Maximum and minimum driver ratings for Prime Sedan bookings
-- Result: max 5.0 | min 3.0
SELECT MAX(Driver_Rating) AS max_driver_rating,
       MIN(Driver_Rating) AS min_driver_rating
FROM rides
WHERE Vehicle_Type = 'Prime Sedan'
  AND Booking_Status = 'Success';


-- Q7. All rides where payment was made using UPI
-- Result: 25,881 rows
SELECT *
FROM rides
WHERE Payment_Method = 'UPI';


-- Q8. Average customer rating per vehicle type
-- Result: Prime Plus 4.009 | Prime Sedan 4.002 | Auto 3.999 | Prime SUV 3.999 | Mini 3.998 | Bike 3.993 | E-Bike 3.988
SELECT Vehicle_Type,
       ROUND(AVG(Customer_Rating), 3) AS avg_customer_rating
FROM rides
WHERE Booking_Status = 'Success'
GROUP BY Vehicle_Type
ORDER BY avg_customer_rating DESC;


-- Q9. Total booking value of rides completed successfully
-- Result: 35,080,467  (note: this includes 3,926 rides flagged "incomplete" inside the Success status,
--         value of fully completed rides only = 32,829,985, see bonus B3)
SELECT SUM(Booking_Value) AS total_success_booking_value
FROM rides
WHERE Booking_Status = 'Success';


-- Q10. All incomplete rides along with the reason
-- Result: 3,926 rows (Customer Demand 1,601 | Vehicle Breakdown 1,591 | Other Issue 734)
SELECT Booking_ID,
       Vehicle_Type,
       Incomplete_Rides_Reason
FROM rides
WHERE Incomplete_Rides = 'Yes';


-- =====================================================================
--  BONUS QUERIES (business-intelligence layer)
-- =====================================================================

-- B1. Booking outcome mix and money attached to each outcome
SELECT Booking_Status,
       COUNT(*)                                            AS bookings,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM rides), 1) AS pct_of_bookings,
       SUM(Booking_Value)                                  AS booking_value
FROM rides
GROUP BY Booking_Status
ORDER BY bookings DESC;


-- B2. Revenue leaked (value of bookings that never completed) by cause
SELECT Booking_Status      AS cause,
       COUNT(*)            AS bookings,
       SUM(Booking_Value)  AS revenue_leaked
FROM rides
WHERE Booking_Status <> 'Success'
GROUP BY Booking_Status
ORDER BY revenue_leaked DESC;


-- B3. Fully completed rides vs rides marked incomplete inside "Success"
SELECT Incomplete_Rides,
       COUNT(*)           AS rides,
       SUM(Booking_Value) AS booking_value
FROM rides
WHERE Booking_Status = 'Success'
GROUP BY Incomplete_Rides;


-- B4. Revenue by payment method (completed rides)
SELECT Payment_Method,
       COUNT(*)           AS rides,
       SUM(Booking_Value) AS revenue,
       ROUND(100.0 * SUM(Booking_Value) / (SELECT SUM(Booking_Value) FROM rides WHERE Booking_Status = 'Success'), 1) AS pct_revenue
FROM rides
WHERE Booking_Status = 'Success'
GROUP BY Payment_Method
ORDER BY revenue DESC;


-- B5. Win-back list: customers with 2+ bookings and zero completed rides
SELECT Customer_ID,
       COUNT(*)           AS attempts,
       SUM(Booking_Value) AS value_lost
FROM rides
GROUP BY Customer_ID
HAVING COUNT(*) >= 2
   AND SUM(CASE WHEN Booking_Status = 'Success' THEN 1 ELSE 0 END) = 0
ORDER BY value_lost DESC;
