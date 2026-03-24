<script setup lang="ts">
import { computed } from 'vue'
import { STATUS_ICON_MAP, resolveIconKey } from './statusIcons'

interface Props {
    name: string
    size?: number
    color?: string
}

const props = withDefaults(defineProps<Props>(), {
    size: 16,
})

const resolved = computed(() => {
    const key = resolveIconKey(props.name)
    return key ? STATUS_ICON_MAP[key] : null
})
</script>

<template>
    <component v-if="resolved" :is="resolved" :size="size" :color="color" :stroke-width="2" />
    <span v-else :style="{ color, fontSize: size + 'px', lineHeight: '1' }">{{ name }}</span>
</template>
