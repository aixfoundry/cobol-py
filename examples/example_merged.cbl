       PROCESS ARITH(EXTEND),OPT,LIST
      *> Merged-grammar smoke test: exercises every preprocessor construct
      *> (compiler options, comment entries, COPY, REPLACE, EXEC CICS/SQL,
      *>  EJECT/SKIP/TITLE) in a single parse pass.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTPROG.
       AUTHOR. JOHN SMITH.
       INSTALLATION. ACME CORPORATION.
       DATE-WRITTEN. 2020-01-01.
       DATE-COMPILED. 2020-06-18.
       SECURITY. NONE.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       INPUT-OUTPUT SECTION.
       DATA DIVISION.
       FILE SECTION.
       WORKING-STORAGE SECTION.
       01  WS-COUNT     PIC 9(4)  VALUE 0.
       COPY MYCOPY.
       REPLACE ==OLD== BY ==NEW==.
       01  WS-OLD       PIC X.
       EXEC SQL
         INCLUDE SQLCA
       END-EXEC.
       PROCEDURE DIVISION.
       MAIN-PARA.
           EJECT
           SKIP1
           TITLE "Sample Report"
           EXEC CICS
             SEND MAP('MYMAP') FROM(WS-OLD)
           END-EXEC
           EXEC SQL
             SELECT COL INTO :WS-COUNT FROM TBL WHERE K = 1
           END-EXEC
           MOVE WS-COUNT TO WS-OLD
           DISPLAY WS-OLD
           STOP RUN.
