SHELL := bash
.PHONY: validate
# Draft manifests (SPEC 11.6). Skipped with a note where the tools are missing (CI has neither).

validate:
	@if command -v kustomize >/dev/null && command -v kubeconform >/dev/null; then \
		kustomize build . | kubeconform -strict -summary -ignore-missing-schemas; \
	elif command -v kubectl >/dev/null && command -v kubeconform >/dev/null; then \
		kubectl kustomize . | kubeconform -strict -summary -ignore-missing-schemas; \
	else \
		echo "deploy: kustomize/kubeconform not installed, skipping validate"; \
	fi
