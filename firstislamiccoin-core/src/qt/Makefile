.PHONY: FORCE
all: FORCE
	$(MAKE) -C .. codexacoin_qt test_codexacoin_qt
clean: FORCE
	$(MAKE) -C .. codexacoin_qt_clean test_codexacoin_qt_clean
check: FORCE
	$(MAKE) -C .. test_codexacoin_qt_check
codexacoin-qt codexacoin-qt.exe: FORCE
	 $(MAKE) -C .. codexacoin_qt
apk: FORCE
	$(MAKE) -C .. codexacoin_qt_apk
