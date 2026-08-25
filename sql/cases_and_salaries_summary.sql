-- cases_and_salaries_summary.sql
-- Podsumowanie wyników fedrowanie-parser (schema v56+)
-- Uruchomienie:
--   sqlite3 fedrowanie_wynagrodzenia_2025.db < cases_and_salaries_summary.sql
--
-- Plik nie modyfikuje danych. Zawiera wyłącznie SELECT-y.

------------------------------------------------------------
-- 1. OGÓLNE PODSUMOWANIE SPRAW
------------------------------------------------------------

.mode box
.headers on

SELECT
    'ALL_CASES' AS metric,
    COUNT(*) AS value
FROM cases_status

UNION ALL

SELECT
    'CASES_WITH_FINAL_SALARY_DATA',
    COUNT(*)
FROM cases_status
WHERE status LIKE 'INDIVIDUAL_ANNUAL_2025%'

UNION ALL

SELECT
    'CASES_WITH_UNPROCESSED_ATTACHMENT',
    COUNT(*)
FROM cases_status
WHERE unprocessed_attachment = 1

UNION ALL

SELECT
    'CASES_WITH_ANY_PROCEDURAL_FLAG',
    COUNT(*)
FROM cases_status
WHERE
       requested_more_time = 1
    OR asked_about_anonymization = 1
    OR requested_clarification = 1
    OR requested_processed_info_justification = 1
    OR fee_notice = 1
    OR transferred_or_not_competent = 1
    OR formal_deficiency_request = 1
    OR refusal_detected = 1
    OR unprocessed_attachment = 1
;

------------------------------------------------------------
-- 2. ROZKŁAD STATUSÓW
------------------------------------------------------------

SELECT
    status,
    COUNT(*) AS case_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS share_pct
FROM cases_status
GROUP BY status
ORDER BY case_count DESC, status
;

------------------------------------------------------------
-- 3. LICZEBNOŚĆ FLAG PROCEDURALNYCH
------------------------------------------------------------

WITH flags AS (
    SELECT 'requested_more_time' AS flag, requested_more_time AS value
    FROM cases_status

    UNION ALL
    SELECT 'asked_about_anonymization', asked_about_anonymization
    FROM cases_status

    UNION ALL
    SELECT 'requested_clarification', requested_clarification
    FROM cases_status

    UNION ALL
    SELECT 'requested_processed_info_justification', requested_processed_info_justification
    FROM cases_status

    UNION ALL
    SELECT 'fee_notice', fee_notice
    FROM cases_status

    UNION ALL
    SELECT 'transferred_or_not_competent', transferred_or_not_competent
    FROM cases_status

    UNION ALL
    SELECT 'formal_deficiency_request', formal_deficiency_request
    FROM cases_status

    UNION ALL
    SELECT 'refusal_detected', refusal_detected
    FROM cases_status

    UNION ALL
    SELECT 'unprocessed_attachment', unprocessed_attachment
    FROM cases_status
)
SELECT
    flag,
    SUM(value) AS case_count,
    ROUND(
        100.0 * SUM(value) / (SELECT COUNT(*) FROM cases_status),
        2
    ) AS share_pct
FROM flags
GROUP BY flag
ORDER BY case_count DESC, flag
;

------------------------------------------------------------
-- 4. STATUS + FLAGI
-- Pokazuje jak przebieg korespondencji łączy się z wynikiem końcowym.
------------------------------------------------------------

SELECT
    status,
    COUNT(*) AS case_count,
    SUM(requested_more_time) AS requested_more_time,
    SUM(asked_about_anonymization) AS asked_about_anonymization,
    SUM(requested_clarification) AS requested_clarification,
    SUM(requested_processed_info_justification) AS requested_processed_info_justification,
    SUM(fee_notice) AS fee_notice,
    SUM(transferred_or_not_competent) AS transferred_or_not_competent,
    SUM(formal_deficiency_request) AS formal_deficiency_request,
    SUM(refusal_detected) AS refusal_detected,
    SUM(unprocessed_attachment) AS unprocessed_attachment
FROM cases_status
GROUP BY status
ORDER BY case_count DESC, status
;

------------------------------------------------------------
-- 5. NAJCZĘSTSZE KOMBINACJE FLAG
------------------------------------------------------------

SELECT
    requested_more_time,
    asked_about_anonymization,
    requested_clarification,
    requested_processed_info_justification,
    fee_notice,
    transferred_or_not_competent,
    formal_deficiency_request,
    refusal_detected,
    unprocessed_attachment,
    COUNT(*) AS case_count
FROM cases_status
GROUP BY
    requested_more_time,
    asked_about_anonymization,
    requested_clarification,
    requested_processed_info_justification,
    fee_notice,
    transferred_or_not_competent,
    formal_deficiency_request,
    refusal_detected,
    unprocessed_attachment
ORDER BY case_count DESC
LIMIT 30
;

------------------------------------------------------------
-- 6. CASE'Y Z NIEPRZETWORZONYMI ZAŁĄCZNIKAMI
------------------------------------------------------------

SELECT
    case_pk,
    institution_pk,
    institution_name,
    status,
    reason,
    parsed_candidate_rows
FROM cases_status
WHERE unprocessed_attachment = 1
ORDER BY institution_name, case_pk
;

------------------------------------------------------------
-- 7. CASE'Y Z PROŚBĄ O WIĘCEJ CZASU
------------------------------------------------------------

SELECT
    case_pk,
    institution_pk,
    institution_name,
    status,
    reason,
    parsed_candidate_rows
FROM cases_status
WHERE requested_more_time = 1
ORDER BY institution_name, case_pk
;

------------------------------------------------------------
-- 8. CASE'Y Z PYTANIEM O ANONIMIZACJĘ
------------------------------------------------------------

SELECT
    case_pk,
    institution_pk,
    institution_name,
    status,
    reason,
    parsed_candidate_rows
FROM cases_status
WHERE asked_about_anonymization = 1
ORDER BY institution_name, case_pk
;

------------------------------------------------------------
-- 9. CASE'Y Z PROŚBĄ O DOPRECYZOWANIE / INFORMACJĘ PRZETWORZONĄ
------------------------------------------------------------

SELECT
    case_pk,
    institution_pk,
    institution_name,
    status,
    requested_clarification,
    requested_processed_info_justification,
    reason
FROM cases_status
WHERE
       requested_clarification = 1
    OR requested_processed_info_justification = 1
ORDER BY institution_name, case_pk
;

------------------------------------------------------------
-- 10. CASE'Y Z ODMOWĄ
------------------------------------------------------------

SELECT
    case_pk,
    institution_pk,
    institution_name,
    status,
    reason
FROM cases_status
WHERE refusal_detected = 1
ORDER BY institution_name, case_pk
;

------------------------------------------------------------
-- 11. OGÓLNE PODSUMOWANIE REKORDÓW WYNAGRODZEŃ
------------------------------------------------------------

SELECT
    'SALARY_ROWS' AS metric,
    COUNT(*) AS value
FROM salaries_extracted

UNION ALL

SELECT
    'INSTITUTIONS_WITH_SALARY_ROWS',
    COUNT(DISTINCT institution_pk)
FROM salaries_extracted

UNION ALL

SELECT
    'ROWS_WITH_DOCTOR_NAME',
    COUNT(*)
FROM salaries_extracted
WHERE NULLIF(TRIM(doctor_name), '') IS NOT NULL

UNION ALL

SELECT
    'ROWS_WITH_DOCTOR_INITIALS',
    COUNT(*)
FROM salaries_extracted
WHERE NULLIF(TRIM(doctor_initials), '') IS NOT NULL

UNION ALL

SELECT
    'ROWS_WITH_SPECIALIZATION',
    COUNT(*)
FROM salaries_extracted
WHERE NULLIF(TRIM(specialization), '') IS NOT NULL

UNION ALL

SELECT
    'ROWS_WITH_CONTRACT_TYPE',
    COUNT(*)
FROM salaries_extracted
WHERE NULLIF(TRIM(contract_type), '') IS NOT NULL

UNION ALL

SELECT
    'ROWS_WITH_ORGANIZATIONAL_UNIT',
    COUNT(*)
FROM salaries_extracted
WHERE NULLIF(TRIM(organizational_unit), '') IS NOT NULL
;

------------------------------------------------------------
-- 12. UZUPEŁNIENIE GŁÓWNYCH PÓL (%)
------------------------------------------------------------

SELECT
    COUNT(*) AS total_rows,

    SUM(NULLIF(TRIM(doctor_name), '') IS NULL) AS doctor_name_nulls,
    ROUND(
        100.0 * SUM(NULLIF(TRIM(doctor_name), '') IS NULL) / COUNT(*),
        2
    ) AS doctor_name_null_pct,

    SUM(NULLIF(TRIM(doctor_initials), '') IS NULL) AS doctor_initials_nulls,
    ROUND(
        100.0 * SUM(NULLIF(TRIM(doctor_initials), '') IS NULL) / COUNT(*),
        2
    ) AS doctor_initials_null_pct,

    SUM(NULLIF(TRIM(specialization), '') IS NULL) AS specialization_nulls,
    ROUND(
        100.0 * SUM(NULLIF(TRIM(specialization), '') IS NULL) / COUNT(*),
        2
    ) AS specialization_null_pct,

    SUM(NULLIF(TRIM(contract_type), '') IS NULL) AS contract_type_nulls,
    ROUND(
        100.0 * SUM(NULLIF(TRIM(contract_type), '') IS NULL) / COUNT(*),
        2
    ) AS contract_type_null_pct,

    SUM(NULLIF(TRIM(organizational_unit), '') IS NULL) AS organizational_unit_nulls,
    ROUND(
        100.0 * SUM(NULLIF(TRIM(organizational_unit), '') IS NULL) / COUNT(*),
        2
    ) AS organizational_unit_null_pct
FROM salaries_extracted
;

------------------------------------------------------------
-- 13. PODSUMOWANIE WYNAGRODZEŃ PER PLACÓWKA
------------------------------------------------------------

SELECT
    institution_pk,
    institution_name,
    record_count,
    total_compensation,
    max_compensation,
    count_above_500k,
    count_above_1m
FROM salaries_summary
ORDER BY total_compensation DESC
;

------------------------------------------------------------
-- 14. GLOBALNE SUMY WYNAGRODZEŃ
------------------------------------------------------------

SELECT
    COUNT(*) AS record_count,
    COUNT(DISTINCT institution_pk) AS institution_count,
    ROUND(
        SUM(COALESCE(gross_compensation, net_compensation)),
        2
    ) AS total_compensation,
    ROUND(
        AVG(COALESCE(gross_compensation, net_compensation)),
        2
    ) AS avg_compensation,
    ROUND(
        MAX(COALESCE(gross_compensation, net_compensation)),
        2
    ) AS max_compensation,
    SUM(
        CASE
            WHEN COALESCE(gross_compensation, net_compensation) > 500000
            THEN 1 ELSE 0
        END
    ) AS count_above_500k,
    SUM(
        CASE
            WHEN COALESCE(gross_compensation, net_compensation) > 1000000
            THEN 1 ELSE 0
        END
    ) AS count_above_1m
FROM salaries_extracted
;

------------------------------------------------------------
-- 15. CASE'Y Z FLAGĄ PROCEDURALNĄ, KTÓRE OSTATECZNIE DOSTARCZYŁY DANE
------------------------------------------------------------

SELECT
    case_pk,
    institution_pk,
    institution_name,
    status,
    requested_more_time,
    asked_about_anonymization,
    requested_clarification,
    requested_processed_info_justification,
    fee_notice,
    transferred_or_not_competent,
    formal_deficiency_request,
    refusal_detected,
    unprocessed_attachment
FROM cases_status
WHERE status LIKE 'INDIVIDUAL_ANNUAL_2025%'
  AND (
       requested_more_time = 1
    OR asked_about_anonymization = 1
    OR requested_clarification = 1
    OR requested_processed_info_justification = 1
    OR fee_notice = 1
    OR transferred_or_not_competent = 1
    OR formal_deficiency_request = 1
    OR refusal_detected = 1
    OR unprocessed_attachment = 1
  )
ORDER BY institution_name, case_pk
;

SELECT DISTINCT
    'https://fedrowanie.siecobywatelska.pl/sprawy/ile-zarabiaja-lekarze-'
        || c.number AS url
FROM cases_status AS cs
JOIN cases AS c
    ON c.pk = cs.case_pk
WHERE cs.unprocessed_attachment = 1
  AND NOT EXISTS (
      SELECT 1
      FROM salaries_extracted AS se
      WHERE se.institution_pk = cs.institution_pk
  )
ORDER BY c.number;