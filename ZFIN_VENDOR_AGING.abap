*&---------------------------------------------------------------------*
*& Report  ZFIN_VENDOR_AGING
*&
*& Description: Vendor Ageing Analysis Report
*&              Shows open items grouped by overdue buckets (30/60/90/120+days)
*&              Used by AP team for month-end closing and vendor reconciliation
*&---------------------------------------------------------------------*
REPORT zfin_vendor_aging NO STANDARD PAGE HEADING LINE-SIZE 255.

TABLES: lfa1, lfb1, bsik, bsak.

TYPE-POOLS: slis.

*----------------------------------------------------------------------*
* SELECTION SCREEN
*----------------------------------------------------------------------*
PARAMETERS: p_bukrs TYPE bukrs OBLIGATORY DEFAULT '1000'.
SELECT-OPTIONS: s_lifnr FOR lfa1-lifnr,
                s_bldat FOR bsik-bldat.
PARAMETERS: p_date  TYPE datum DEFAULT sy-datum.

*----------------------------------------------------------------------*
* DATA DECLARATIONS
*----------------------------------------------------------------------*
DATA: BEGIN OF gt_open_items OCCURS 0,
        lifnr TYPE lfa1-lifnr,
        name1 TYPE lfa1-name1,
        belnr TYPE bsik-belnr,
        bldat TYPE bsik-bldat,
        faedt TYPE bsik-faedt,
        wrbtr TYPE bsik-wrbtr,
        waers TYPE bsik-waers,
        days_overdue TYPE i,
        bucket TYPE c LENGTH 10,
      END OF gt_open_items.

DATA: gt_fieldcat TYPE slis_t_fieldcat_alv,
      gs_layout   TYPE slis_layout_alv,
      gt_sort     TYPE slis_t_sortinfo_alv.

DATA: gv_days TYPE i.

*----------------------------------------------------------------------*
* START-OF-SELECTION
*----------------------------------------------------------------------*
START-OF-SELECTION.
  PERFORM fetch_open_items.
  PERFORM calculate_aging.
  PERFORM display_alv.

*----------------------------------------------------------------------*
* FORM FETCH_OPEN_ITEMS
*----------------------------------------------------------------------*
FORM fetch_open_items.

  SELECT b~lifnr l~name1 b~belnr b~bldat b~faedt b~wrbtr b~waers
    INTO CORRESPONDING FIELDS OF TABLE gt_open_items
    FROM bsik AS b
    INNER JOIN lfa1 AS l ON l~lifnr = b~lifnr
    WHERE b~bukrs = p_bukrs
      AND b~lifnr IN s_lifnr
      AND b~bldat IN s_bldat.

  IF sy-subrc <> 0.
    MESSAGE 'No open vendor items found' TYPE 'I'.
  ENDIF.

ENDFORM.                    "fetch_open_items

*----------------------------------------------------------------------*
* FORM CALCULATE_AGING
*----------------------------------------------------------------------*
FORM calculate_aging.

  LOOP AT gt_open_items.
    gv_days = p_date - gt_open_items-faedt.
    gt_open_items-days_overdue = gv_days.

    CASE gv_days.
      WHEN 0.
        gt_open_items-bucket = 'Current'.
      WHEN 1 TO 30.
        gt_open_items-bucket = '1-30'.
      WHEN 31 TO 60.
        gt_open_items-bucket = '31-60'.
      WHEN 61 TO 90.
        gt_open_items-bucket = '61-90'.
      WHEN 91 TO 120.
        gt_open_items-bucket = '91-120'.
      WHEN OTHERS.
        gt_open_items-bucket = '120+'.
    ENDCASE.

    MODIFY gt_open_items.
  ENDLOOP.

ENDFORM.                    "calculate_aging

*----------------------------------------------------------------------*
* FORM DISPLAY_ALV
*----------------------------------------------------------------------*
FORM display_alv.

  PERFORM build_fieldcat.

  gs_layout-colwidth_optimize = 'X'.
  gs_layout-zebra             = 'X'.
  gs_layout-box_fieldname     = 'SEL'.

  CALL FUNCTION 'REUSE_ALV_GRID_DISPLAY'
    EXPORTING
      i_callback_program = sy-repid
      is_layout          = gs_layout
      it_fieldcat        = gt_fieldcat
      it_sort            = gt_sort
    TABLES
      t_outtab           = gt_open_items
    EXCEPTIONS
      program_error      = 1
      OTHERS             = 2.

  IF sy-subrc <> 0.
    MESSAGE ID sy-msgid TYPE sy-msgty NUMBER sy-msgno
            WITH sy-msgv1 sy-msgv2 sy-msgv3 sy-msgv4.
  ENDIF.

ENDFORM.                    "display_alv

*----------------------------------------------------------------------*
* FORM BUILD_FIELDCAT
*----------------------------------------------------------------------*
FORM build_fieldcat.

  DATA: ls_fcat TYPE slis_fieldcat_alv.

  CLEAR ls_fcat.
  ls_fcat-col_pos   = 1.
  ls_fcat-fieldname = 'LIFNR'.
  ls_fcat-seltext_l = 'Vendor'.
  APPEND ls_fcat TO gt_fieldcat.

  CLEAR ls_fcat.
  ls_fcat-col_pos   = 2.
  ls_fcat-fieldname = 'NAME1'.
  ls_fcat-seltext_l = 'Vendor Name'.
  APPEND ls_fcat TO gt_fieldcat.

  CLEAR ls_fcat.
  ls_fcat-col_pos   = 3.
  ls_fcat-fieldname = 'BELNR'.
  ls_fcat-seltext_l = 'Document No'.
  APPEND ls_fcat TO gt_fieldcat.

  CLEAR ls_fcat.
  ls_fcat-col_pos   = 4.
  ls_fcat-fieldname = 'BLDAT'.
  ls_fcat-seltext_l = 'Doc Date'.
  APPEND ls_fcat TO gt_fieldcat.

  CLEAR ls_fcat.
  ls_fcat-col_pos   = 5.
  ls_fcat-fieldname = 'FAEDT'.
  ls_fcat-seltext_l = 'Due Date'.
  APPEND ls_fcat TO gt_fieldcat.

  CLEAR ls_fcat.
  ls_fcat-col_pos   = 6.
  ls_fcat-fieldname = 'WRBTR'.
  ls_fcat-seltext_l = 'Amount'.
  ls_fcat-do_sum    = 'X'.
  APPEND ls_fcat TO gt_fieldcat.

  CLEAR ls_fcat.
  ls_fcat-col_pos   = 7.
  ls_fcat-fieldname = 'WAERS'.
  ls_fcat-seltext_l = 'Currency'.
  APPEND ls_fcat TO gt_fieldcat.

  CLEAR ls_fcat.
  ls_fcat-col_pos   = 8.
  ls_fcat-fieldname = 'DAYS_OVERDUE'.
  ls_fcat-seltext_l = 'Days Overdue'.
  APPEND ls_fcat TO gt_fieldcat.

  CLEAR ls_fcat.
  ls_fcat-col_pos   = 9.
  ls_fcat-fieldname = 'BUCKET'.
  ls_fcat-seltext_l = 'Aging Bucket'.
  APPEND ls_fcat TO gt_fieldcat.

ENDFORM.                    "build_fieldcat