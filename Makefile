all:	install install_system

install: is_normal
	cp -pr pi/usr/local/bin/* /usr/local/bin/

install_system: is_normal
	sudo cp -pr pi/etc/* /etc/
	sudo cp -pr pi/lib/* /lib/

is_normal:
	@if test `sysstate` != "normal"; then \
	    echo "warning: / is not writeable; reboot with reboot_n to make permanent changes"; \
		echo "... will continue in 3s.... "; sleep 3; \
	fi
